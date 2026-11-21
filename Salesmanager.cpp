// Handles the process of selling a product.

#include "SalesManager.h"

#include <iomanip>
#include <iostream>

#include "Utils.h"

using std::cout;

SalesManager::SalesManager(ProductManager* pm, FileManager* fm)
    : productManager(pm), fileManager(fm), nextSaleId(1) {}

bool SalesManager::loadHistory() {
    history.clear();
    int skipped = 0;
    if (!fileManager->loadSalesFromFile(history, skipped)) return false;
    nextSaleId = 1;
    for (std::size_t i = 0; i < history.size(); ++i) {
        if (history[i].saleId >= nextSaleId) nextSaleId = history[i].saleId + 1;
    }
    return true;
}

int SalesManager::getSalesCount() const {
    return static_cast<int>(history.size());
}

bool SalesManager::sellProductInteractive(SaleRecord& completedSale) {
    cout << "\n--- Sell a Product ---\n";
    if (productManager->getProductCount() == 0) {
        cout << "There are no products in the store yet.\n";
        return false;
    }
    int id = Utils::readInt("Enter product ID to sell: ", 1, ProductManager::MAX_PRODUCT_ID);
    Product* product = productManager->findProductById(id);   // binary search
    if (product == nullptr) {
        cout << "Product with ID " << id << " was not found. Sale cancelled.\n";
        return false;
    }
    cout << "Product : " << product->name << " (" << product->category << ")\n";
    cout << "In stock: " << product->quantity << "\n";
    cout << "Price   : Rs " << Utils::formatMoney(product->discountedPrice);
    if (product->discountedPrice < product->price) {
        cout << " (discounted from Rs " << Utils::formatMoney(product->price) << ")";
    }
    cout << "\n";
    if (product->quantity == 0) {
        cout << "This product is out of stock. Sale cancelled.\n";
        return false;
    }

    int quantity = Utils::readInt("Quantity to sell: ", 1, ProductManager::MAX_QUANTITY);
    if (quantity > product->quantity) {
        cout << "Insufficient stock: only " << product->quantity << " available, requested "
             << quantity << ". Sale cancelled.\n";
        return false;
    }

    double unitPrice = product->discountedPrice;
    double total = Utils::roundMoney(unitPrice * quantity);
    cout << "Bill: " << quantity << " x Rs " << Utils::formatMoney(unitPrice)
         << " = Rs " << Utils::formatMoney(total) << "\n";
    if (!Utils::readYesNo("Confirm sale? (y/n): ")) {
        cout << "Sale cancelled.\n";
        return false;
    }

    product->quantity -= quantity;
    if (!productManager->saveToFile()) {
        product->quantity += quantity;     // roll back: an unsaved sale is not a completed sale
        cout << "Sale cancelled because stock could not be saved.\n";
        return false;
    }

    SaleRecord sale;
    sale.saleId = nextSaleId++;
    sale.dateTime = Utils::getSystemDateTime();
    sale.productId = product->id;
    sale.productName = product->name;
    sale.quantity = quantity;
    sale.unitPrice = unitPrice;
    sale.totalBill = total;
    history.push_back(sale);
    if (!fileManager->saveSalesToFile(sale)) {
        cout << "Warning: the sale could not be written to sales.txt.\n";
    }

    cout << "Sale completed. Sale ID " << sale.saleId << ", total Rs " << Utils::formatMoney(total) << ".\n";
    if (product->quantity <= product->reorderLevel) {
        cout << "WARNING: stock of '" << product->name << "' is now " << product->quantity
             << " (reorder level " << product->reorderLevel << ").\n";
    }
    completedSale = sale;
    return true;
}

void SalesManager::displaySalesHistory() const {
    cout << "\n--- Sales History ---\n";
    if (history.empty()) {
        cout << "No sales have been recorded yet.\n";
        return;
    }
    cout << std::left << std::setw(8) << "SaleID" << std::setw(21) << "Date/Time" << std::setw(8)
         << "ProdID" << std::setw(22) << "Product" << std::right << std::setw(5) << "Qty"
         << std::setw(11) << "Unit Rs" << std::setw(12) << "Total Rs" << "\n";
    cout << std::string(87, '-') << "\n";
    double revenue = 0.0;
    for (std::size_t i = 0; i < history.size(); ++i) {
        const SaleRecord& s = history[i];
        cout << std::left << std::setw(8) << s.saleId << std::setw(21) << s.dateTime << std::setw(8)
             << s.productId << std::setw(22) << Utils::truncate(s.productName, 20) << std::right
             << std::setw(5) << s.quantity << std::setw(11) << Utils::formatMoney(s.unitPrice)
             << std::setw(12) << Utils::formatMoney(s.totalBill) << "\n";
        revenue += s.totalBill;
    }
    cout << "Total sales: " << history.size() << "   Total revenue: Rs " << Utils::formatMoney(revenue) << "\n";
}

// Reverses the most recent sale: stock is returned and the record is removed from history/file.
bool SalesManager::undoSale(const SaleRecord& sale) {
    if (history.empty() || history.back().saleId != sale.saleId) {
        cout << "Cannot undo: this is not the most recent sale.\n";
        return false;
    }
    Product* product = productManager->findProductById(sale.productId);
    if (product == nullptr) {
        cout << "Cannot undo: product " << sale.productId << " no longer exists.\n";
        return false;
    }
    product->quantity += sale.quantity;
    history.pop_back();
    nextSaleId = sale.saleId;
    bool productsSaved = productManager->saveToFile();
    bool salesSaved = fileManager->saveAllSalesToFile(history);
    if (!productsSaved || !salesSaved) {
        cout << "Warning: the undo was applied in memory but a file could not be updated.\n";
    }
    return true;
}
