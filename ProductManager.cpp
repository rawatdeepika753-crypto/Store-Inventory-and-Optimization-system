#include "ProductManager.h"

#include <algorithm>
#include <iomanip>
#include <iostream>

#include "Utils.h"

using std::cout;

namespace {

void printProductHeader() {
    cout << std::left << std::setw(8) << "ID" << std::setw(22) << "Name" << std::setw(15) << "Category"
         << std::right << std::setw(6) << "Qty" << std::setw(9) << "Reorder" << std::setw(10) << "Price"
         << std::setw(12) << "Disc.Price" << "  " << std::left << "Expiry" << "\n";
    cout << std::string(86, '-') << "\n";
}

void printProductRow(const Product& p) {
    cout << std::left << std::setw(8) << p.id << std::setw(22) << Utils::truncate(p.name, 20)
         << std::setw(15) << Utils::truncate(p.category, 13) << std::right << std::setw(6) << p.quantity
         << std::setw(9) << p.reorderLevel << std::setw(10) << Utils::formatMoney(p.price)
         << std::setw(12) << Utils::formatMoney(p.discountedPrice) << "  " << std::left << p.expiryDate << "\n";
}

bool sameValues(const Product& a, const Product& b) {
    return a.name == b.name && a.category == b.category && a.quantity == b.quantity &&
           a.reorderLevel == b.reorderLevel && a.price == b.price &&
           a.discountedPrice == b.discountedPrice && a.expiryDate == b.expiryDate;
}

}  // namespace

ProductManager::ProductManager(FileManager* fm)
    : fileManager(fm), head(nullptr), productCount(0), indexValid(false) {}

ProductManager::~ProductManager() {
    clearList();
}

void ProductManager::clearList() {
    invalidateIndex();
    while (head != nullptr) {
        Product* toDelete = head;
        head = head->next;
        delete toDelete;
    }
    productCount = 0;
}

void ProductManager::invalidateIndex() {
    searchIndex.clear();     // drop all node pointers BEFORE any node is deleted
    indexValid = false;
}

// ---------- File storage ----------

bool ProductManager::loadFromFile() {
    clearList();
    int skipped = 0;
    if (!fileManager->loadProductsFromFile(head, skipped)) {
        return false;
    }
    productCount = 0;
    for (Product* c = head; c != nullptr; c = c->next) ++productCount;
    invalidateIndex();
    return true;
}

bool ProductManager::saveToFile() const {
    return fileManager->saveProductsToFile(head);
}

// ---------- Binary search ----------

// Builds an array of (id, node pointer) from the linked list and sorts it by id: O(n log n).
void ProductManager::rebuildSearchIndex() {
    searchIndex.clear();
    for (Product* c = head; c != nullptr; c = c->next) {
        IndexEntry entry;
        entry.id = c->id;
        entry.node = c;
        searchIndex.push_back(entry);
    }
    std::sort(searchIndex.begin(), searchIndex.end(),
              [](const IndexEntry& a, const IndexEntry& b) { return a.id < b.id; });
    indexValid = true;
}

// Binary search on the sorted index: O(log n) per lookup.
// The returned pointer must be used immediately; it is not valid after a delete.
Product* ProductManager::findProductById(int id) {
    if (!indexValid) rebuildSearchIndex();
    int low = 0;
    int high = static_cast<int>(searchIndex.size()) - 1;
    while (low <= high) {
        int mid = low + (high - low) / 2;
        if (searchIndex[mid].id == id) return searchIndex[mid].node;
        if (searchIndex[mid].id < id) low = mid + 1;
        else high = mid - 1;
    }
    return nullptr;
}

// ---------- Core list operations ----------

bool ProductManager::insertProduct(const Product& product) {
    if (product.id <= 0 || findProductById(product.id) != nullptr) return false;
    Product* node = new Product(product);
    node->next = nullptr;
    if (head == nullptr) {
        head = node;
    } else {
        Product* tail = head;
        while (tail->next != nullptr) tail = tail->next;
        tail->next = node;
    }
    ++productCount;
    invalidateIndex();
    return true;
}

bool ProductManager::deleteProductById(int id) {
    Product* previous = nullptr;
    Product* current = head;
    while (current != nullptr && current->id != id) {
        previous = current;
        current = current->next;
    }
    if (current == nullptr) return false;

    invalidateIndex();               // no dangling pointers survive the delete
    if (previous == nullptr) head = current->next;
    else previous->next = current->next;
    delete current;
    --productCount;
    return true;
}

bool ProductManager::restoreProduct(const Product& snapshot) {
    Product* node = findProductById(snapshot.id);
    if (node == nullptr) return false;
    Product* oldNext = node->next;
    *node = snapshot;
    node->next = oldNext;            // keep the list links intact
    return true;
}

Product* ProductManager::getHead() const {
    return head;
}

int ProductManager::getProductCount() const {
    return productCount;
}

// ---------- Menu operations ----------

int ProductManager::addProductInteractive() {
    cout << "\n--- Add New Product ---\n";
    Product product;
    product.id = Utils::readInt("Product ID (1-999999): ", 1, MAX_PRODUCT_ID);
    if (findProductById(product.id) != nullptr) {
        cout << "A product with ID " << product.id << " already exists. Nothing was added.\n";
        return 0;
    }
    product.name = Utils::readText("Product name: ");
    product.category = Utils::readText("Category: ");
    product.quantity = Utils::readInt("Quantity in stock: ", 0, MAX_QUANTITY);
    product.reorderLevel = Utils::readInt("Reorder level (warn when stock is at or below this): ", 1, MAX_QUANTITY);
    product.price = Utils::roundMoney(Utils::readDouble("Price (Rs): ", 0.01));
    product.discountedPrice = product.price;
    product.expiryDate = Utils::readExpiryDate("Expiry date (YYYY-MM-DD, or NA if it does not expire): ");

    if (!insertProduct(product)) {
        cout << "Could not add the product.\n";
        return 0;
    }
    cout << "Product added successfully.\n";
    if (!saveToFile()) cout << "Warning: the product is in memory but could not be saved to file.\n";
    return product.id;
}

void ProductManager::displayAllProducts() const {
    cout << "\n--- All Products ---\n";
    if (head == nullptr) {
        cout << "No products found.\n";
        return;
    }
    printProductHeader();
    for (const Product* c = head; c != nullptr; c = c->next) printProductRow(*c);
    cout << "Total products: " << productCount << "\n";
}

void ProductManager::searchProductInteractive() {
    cout << "\n--- Search Product by ID ---\n";
    int id = Utils::readInt("Enter product ID: ", 1, MAX_PRODUCT_ID);
    Product* product = findProductById(id);
    if (product == nullptr) {
        cout << "Product with ID " << id << " was not found.\n";
        return;
    }
    cout << "Product found:\n";
    printProductHeader();
    printProductRow(*product);
}

bool ProductManager::updateProductInteractive(Product& beforeChange) {
    cout << "\n--- Update Product ---\n";
    int id = Utils::readInt("Enter product ID to update: ", 1, MAX_PRODUCT_ID);
    Product* product = findProductById(id);
    if (product == nullptr) {
        cout << "Product with ID " << id << " was not found.\n";
        return false;
    }
    cout << "Current details:\n";
    printProductHeader();
    printProductRow(*product);
    cout << "Press Enter to keep the current value of a field.\n";

    Product updated = *product;
    updated.name = Utils::readText("Name [" + product->name + "]: ", &product->name);
    updated.category = Utils::readText("Category [" + product->category + "]: ", &product->category);
    updated.quantity = Utils::readInt("Quantity [" + std::to_string(product->quantity) + "]: ",
                                      0, MAX_QUANTITY, &product->quantity);
    updated.reorderLevel = Utils::readInt("Reorder level [" + std::to_string(product->reorderLevel) + "]: ",
                                          1, MAX_QUANTITY, &product->reorderLevel);
    updated.price = Utils::roundMoney(Utils::readDouble("Price [" + Utils::formatMoney(product->price) + "]: ",
                                                        0.01, &product->price));
    updated.expiryDate = Utils::readExpiryDate("Expiry date [" + product->expiryDate + "]: ", &product->expiryDate);

    if (updated.price != product->price || updated.expiryDate != product->expiryDate) {
        updated.discountedPrice = updated.price;   // a new price or expiry date resets any discount
        cout << "Note: discounted price was reset to the (new) normal price.\n";
    }
    if (sameValues(updated, *product)) {
        cout << "No changes were made.\n";
        return false;
    }

    beforeChange = *product;
    beforeChange.next = nullptr;
    restoreProduct(updated);         // writes the new values into the existing node
    cout << "Product updated successfully.\n";
    if (!saveToFile()) cout << "Warning: the change is in memory but could not be saved to file.\n";
    return true;
}

bool ProductManager::deleteProductInteractive(Product& deletedCopy) {
    cout << "\n--- Delete Product ---\n";
    int id = Utils::readInt("Enter product ID to delete: ", 1, MAX_PRODUCT_ID);
    Product* product = findProductById(id);
    if (product == nullptr) {
        cout << "Product with ID " << id << " was not found.\n";
        return false;
    }
    printProductHeader();
    printProductRow(*product);
    if (!Utils::readYesNo("Delete this product? (y/n): ")) {
        cout << "Delete cancelled.\n";
        return false;
    }
    deletedCopy = *product;
    deletedCopy.next = nullptr;
    deleteProductById(id);           // 'product' pointer must not be used after this line
    cout << "Product deleted successfully.\n";
    if (!saveToFile()) cout << "Warning: the change is in memory but could not be saved to file.\n";
    return true;
}
