#include "InventoryManager.h"

#include <algorithm>
#include <iomanip>
#include <iostream>

#include "Utils.h"

using std::cout;

namespace {

bool isLowStock(const Product& p) {
    return p.quantity <= p.reorderLevel;
}

bool hasDiscount(const Product& p) {
    return p.discountedPrice < p.price - 0.005;
}

// Returns days from 'today' to the expiry date, or false if the product never expires.
bool daysUntilExpiry(const Product& p, const std::string& today, int& days) {
    if (p.expiryDate == "NA") return false;
    days = Utils::daysBetween(today, p.expiryDate);
    return true;
}

bool isEligibleForDiscount(const Product& p, int daysLeft) {
    return daysLeft >= 0 && daysLeft <= InventoryManager::NEAR_EXPIRY_DAYS && !hasDiscount(p);
}

}  // namespace

InventoryManager::InventoryManager(ProductManager* pm, FileManager* fm)
    : productManager(pm), fileManager(fm), nextRequestId(1) {}

int InventoryManager::calculateTargetStock(const Product& product) {
    int target = product.reorderLevel * TARGET_STOCK_MULTIPLIER;
    return std::max(target, product.reorderLevel + 1);
}

// ---------- Persistence ----------

bool InventoryManager::loadRestockRequests() {
    while (!pendingRequests.empty()) pendingRequests.pop();
    closedRequests.clear();
    int skipped = 0;
    if (!fileManager->loadRestockFromFile(pendingRequests, closedRequests, skipped)) return false;

    nextRequestId = 1;
    for (std::size_t i = 0; i < closedRequests.size(); ++i) {
        nextRequestId = std::max(nextRequestId, closedRequests[i].requestId + 1);
    }
    std::queue<RestockRequest> copy = pendingRequests;
    while (!copy.empty()) {
        nextRequestId = std::max(nextRequestId, copy.front().requestId + 1);
        copy.pop();
    }
    return true;
}

bool InventoryManager::saveRestockRequests() const {
    return fileManager->saveRestockToFile(pendingRequests, closedRequests);
}

int InventoryManager::getPendingCount() const {
    return static_cast<int>(pendingRequests.size());
}

bool InventoryManager::hasPendingRequest(int productId) const {
    std::queue<RestockRequest> copy = pendingRequests;
    while (!copy.empty()) {
        if (copy.front().productId == productId) return true;
        copy.pop();
    }
    return false;
}

// ---------- Stock checks ----------

void InventoryManager::displayInventoryStatus() const {
    cout << "\n--- Inventory Status ---\n";
    const Product* head = productManager->getHead();
    if (head == nullptr) {
        cout << "No products found.\n";
        return;
    }
    cout << std::left << std::setw(8) << "ID" << std::setw(22) << "Name" << std::right << std::setw(6)
         << "Qty" << std::setw(9) << "Reorder" << "  " << std::left << std::setw(14) << "Status"
         << std::setw(12) << "Expiry" << "Pending restock\n";
    cout << std::string(86, '-') << "\n";
    int low = 0, outOfStock = 0, totalUnits = 0, count = 0;
    for (const Product* c = head; c != nullptr; c = c->next) {
        std::string status = "OK";
        if (c->quantity == 0) { status = "OUT OF STOCK"; ++outOfStock; ++low; }
        else if (isLowStock(*c)) { status = "LOW STOCK"; ++low; }
        cout << std::left << std::setw(8) << c->id << std::setw(22) << Utils::truncate(c->name, 20)
             << std::right << std::setw(6) << c->quantity << std::setw(9) << c->reorderLevel << "  "
             << std::left << std::setw(14) << status << std::setw(12) << c->expiryDate
             << (hasPendingRequest(c->id) ? "yes" : "no") << "\n";
        totalUnits += c->quantity;
        ++count;
    }
    cout << "\nProducts: " << count << "   Total units in stock: " << totalUnits
         << "   Pending restock requests: " << pendingRequests.size() << "\n";
    if (low > 0) {
        cout << "WARNING: " << low << " product(s) are at or below the reorder level";
        if (outOfStock > 0) cout << " (" << outOfStock << " out of stock)";
        cout << ".\n";
    } else {
        cout << "All products are above their reorder levels.\n";
    }
}

int InventoryManager::checkLowStock() const {
    cout << "\n--- Low Stock Check ---\n";
    cout << "Rule: warning when quantity <= reorder level. Target stock = "
         << TARGET_STOCK_MULTIPLIER << " x reorder level.\n";
    int count = 0;
    for (const Product* c = productManager->getHead(); c != nullptr; c = c->next) {
        if (!isLowStock(*c)) continue;
        if (count == 0) {
            cout << std::left << std::setw(8) << "ID" << std::setw(22) << "Name" << std::right
                 << std::setw(6) << "Qty" << std::setw(9) << "Reorder" << std::setw(8) << "Target"
                 << std::setw(12) << "Need" << "  " << std::left << "Request pending?\n";
            cout << std::string(80, '-') << "\n";
        }
        int target = calculateTargetStock(*c);
        cout << std::left << std::setw(8) << c->id << std::setw(22) << Utils::truncate(c->name, 20)
             << std::right << std::setw(6) << c->quantity << std::setw(9) << c->reorderLevel
             << std::setw(8) << target << std::setw(12) << (target - c->quantity) << "  " << std::left
             << (hasPendingRequest(c->id) ? "yes" : "no") << "\n";
        ++count;
    }
    if (count == 0) cout << "No products are low on stock.\n";
    else cout << "WARNING: " << count << " product(s) need restocking.\n";
    return count;
}

// ---------- Restock queue ----------

int InventoryManager::createRestockRequests() {
    cout << "\n--- Create Restock Requests ---\n";
    int created = 0, alreadyPending = 0;
    std::string today = Utils::getSystemDate();
    for (const Product* c = productManager->getHead(); c != nullptr; c = c->next) {
        if (!isLowStock(*c)) continue;
        if (hasPendingRequest(c->id)) { ++alreadyPending; continue; }
        RestockRequest request;
        request.requestId = nextRequestId++;
        request.productId = c->id;
        request.productName = c->name;
        request.currentQuantity = c->quantity;
        request.requestedQuantity = calculateTargetStock(*c) - c->quantity;
        request.dateRequested = today;
        request.status = "PENDING";
        request.dateClosed = "-";
        pendingRequests.push(request);          // enqueue (FIFO)
        cout << "Request #" << request.requestId << ": " << c->name << " - order "
             << request.requestedQuantity << " units (stock " << c->quantity << " -> target "
             << calculateTargetStock(*c) << ")\n";
        ++created;
    }
    if (created == 0) cout << "No new restock requests were needed.\n";
    if (alreadyPending > 0) cout << alreadyPending << " low-stock product(s) already have a pending request.\n";
    if (created > 0 && !saveRestockRequests()) cout << "Warning: restock.txt could not be updated.\n";
    return created;
}

void InventoryManager::displayRestockRequests() const {
    cout << "\n--- Restock Requests ---\n";
    cout << "Pending (first in queue = next to be received): " << pendingRequests.size() << "\n";
    if (!pendingRequests.empty()) {
        cout << std::left << std::setw(5) << "Pos" << std::setw(8) << "Req#" << std::setw(8) << "ProdID"
             << std::setw(22) << "Product" << std::right << std::setw(9) << "Current" << std::setw(10)
             << "Order qty" << "  " << std::left << "Requested on\n";
        cout << std::string(80, '-') << "\n";
        std::queue<RestockRequest> copy = pendingRequests;
        int position = 1;
        while (!copy.empty()) {
            const RestockRequest& r = copy.front();
            cout << std::left << std::setw(5) << position++ << std::setw(8) << r.requestId << std::setw(8)
                 << r.productId << std::setw(22) << Utils::truncate(r.productName, 20) << std::right
                 << std::setw(9) << r.currentQuantity << std::setw(10) << r.requestedQuantity << "  "
                 << std::left << r.dateRequested << "\n";
            copy.pop();
        }
    }
    cout << "\nClosed requests (history): " << closedRequests.size() << "\n";
    for (std::size_t i = 0; i < closedRequests.size(); ++i) {
        const RestockRequest& r = closedRequests[i];
        cout << "  #" << r.requestId << " " << r.productName << " (ID " << r.productId << ") +"
             << r.requestedQuantity << "  " << r.status << " on " << r.dateClosed << "\n";
    }
}

bool InventoryManager::fulfillNextRestockRequest() {
    cout << "\n--- Receive Next Restock ---\n";
    if (pendingRequests.empty()) {
        cout << "There are no pending restock requests.\n";
        return false;
    }
    RestockRequest request = pendingRequests.front();
    Product* product = productManager->findProductById(request.productId);
    bool stockChanged = false;

    if (product == nullptr) {
        request.status = "CANCELLED";
        cout << "Request #" << request.requestId << " was cancelled: product ID "
             << request.productId << " no longer exists.\n";
    } else {
        product->quantity += request.requestedQuantity;
        if (!productManager->saveToFile()) {
            product->quantity -= request.requestedQuantity;   // roll back, keep request pending
            cout << "Could not save products.txt. The request stays pending.\n";
            return false;
        }
        request.status = "FULFILLED";
        stockChanged = true;
        cout << "Request #" << request.requestId << " fulfilled: " << product->name << " stock is now "
             << product->quantity << ".\n";
    }
    pendingRequests.pop();                                    // dequeue
    request.dateClosed = Utils::getSystemDate();
    closedRequests.push_back(request);
    if (!saveRestockRequests()) cout << "Warning: restock.txt could not be updated.\n";
    return stockChanged;
}

// ---------- Expiry and discounts ----------

void InventoryManager::analyzeExpiry(const std::string& today) const {
    cout << "\n--- Expiry Analysis (as of " << today << ") ---\n";
    cout << "Near expiry = " << NEAR_EXPIRY_DAYS << " days or fewer left. Discount = "
         << DISCOUNT_PERCENT << "%.\n";
    int expired = 0, near = 0, withExpiry = 0, shown = 0;
    for (const Product* c = productManager->getHead(); c != nullptr; c = c->next) {
        int days = 0;
        if (!daysUntilExpiry(*c, today, days)) continue;
        ++withExpiry;
        std::string status;
        if (days < 0) { status = "EXPIRED"; ++expired; }
        else if (days <= NEAR_EXPIRY_DAYS) {
            status = hasDiscount(*c) ? "NEAR EXPIRY (discounted)" : "NEAR EXPIRY (eligible)";
            ++near;
        } else continue;                         // only list products needing attention
        if (shown == 0) {
            cout << std::left << std::setw(8) << "ID" << std::setw(22) << "Name" << std::setw(12)
                 << "Expiry" << std::right << std::setw(10) << "Days left" << "  " << std::left
                 << std::setw(26) << "Status" << std::right << std::setw(9) << "Price"
                 << std::setw(10) << "Now" << "\n";
            cout << std::string(99, '-') << "\n";
        }
        ++shown;
        cout << std::left << std::setw(8) << c->id << std::setw(22) << Utils::truncate(c->name, 20)
             << std::setw(12) << c->expiryDate << std::right << std::setw(10) << days << "  "
             << std::left << std::setw(26) << status << std::right << std::setw(9)
             << Utils::formatMoney(c->price) << std::setw(10) << Utils::formatMoney(c->discountedPrice) << "\n";
    }
    if (withExpiry == 0) cout << "No products have an expiry date.\n";
    else if (shown == 0) cout << "No products are expired or near expiry.\n";
    if (expired > 0) cout << "WARNING: " << expired << " product(s) are EXPIRED and should be removed from sale.\n";
    if (near > 0) cout << "NOTICE: " << near << " product(s) are near expiry.\n";
}

int InventoryManager::applyNearExpiryDiscounts(const std::string& today) {
    int eligible = 0;
    for (const Product* c = productManager->getHead(); c != nullptr; c = c->next) {
        int days = 0;
        if (daysUntilExpiry(*c, today, days) && isEligibleForDiscount(*c, days)) ++eligible;
    }
    if (eligible == 0) {
        cout << "No products are eligible for a discount.\n";
        return 0;
    }
    cout << eligible << " product(s) are eligible for a " << DISCOUNT_PERCENT << "% discount.\n";
    if (!Utils::readYesNo("Apply the discount now? (y/n): ")) {
        cout << "No discount applied.\n";
        return 0;
    }
    for (Product* c = productManager->getHead(); c != nullptr; c = c->next) {
        int days = 0;
        if (daysUntilExpiry(*c, today, days) && isEligibleForDiscount(*c, days)) {
            c->discountedPrice = Utils::roundMoney(c->price * (100 - DISCOUNT_PERCENT) / 100.0);
            cout << "  " << c->name << ": Rs " << Utils::formatMoney(c->price) << " -> Rs "
                 << Utils::formatMoney(c->discountedPrice) << "\n";
        }
    }
    if (!productManager->saveToFile()) cout << "Warning: discounts are in memory but could not be saved.\n";
    else cout << "Discounts applied and saved.\n";
    return eligible;
}
