#include "SystemManager.h"

#include <iostream>

#include "Utils.h"

using std::cout;

SystemManager::SystemManager(const std::string& dataFolder)
    : fileManager(dataFolder),
      productManager(&fileManager),
      salesManager(&productManager, &fileManager),
      inventoryManager(&productManager, &fileManager) {}

bool SystemManager::initialize() {
    cout << "Starting Store Inventory and Optimization System...\n";
    if (!fileManager.initializeFiles()) return false;
    if (!productManager.loadFromFile()) return false;
    if (!salesManager.loadHistory()) return false;
    if (!inventoryManager.loadRestockRequests()) return false;
    cout << "Loaded " << productManager.getProductCount() << " product(s), "
         << salesManager.getSalesCount() << " sale record(s) and "
         << inventoryManager.getPendingCount() << " pending restock request(s).\n";
    return true;
}

void SystemManager::showMainMenu() const {
    cout << "\n==========================================\n";
    cout << "  STORE INVENTORY AND OPTIMIZATION SYSTEM\n";
    cout << "==========================================\n";
    cout << " 1. Product Management\n";
    cout << " 2. Sell a Product\n";
    cout << " 3. Inventory and Restocking\n";
    cout << " 4. Expiry and Discount Analysis\n";
    cout << " 5. View Sales History\n";
    cout << " 6. View Restock Requests\n";
    cout << " 7. Undo Last Supported Operation\n";
    cout << " 8. Save Data\n";
    cout << " 9. Exit\n";
}

void SystemManager::run() {
    bool running = true;
    while (running) {
        showMainMenu();
        int choice = Utils::readInt("Enter your choice (1-9): ", 1, 9);
        switch (choice) {
            case 1: productMenu(); break;
            case 2: sellProduct(); break;
            case 3: inventoryMenu(); break;
            case 4: expiryMenu(); break;
            case 5: salesManager.displaySalesHistory(); break;
            case 6: inventoryManager.displayRestockRequests(); break;
            case 7: undoLastOperation(); break;
            case 8:
                if (saveAllData()) cout << "All data saved.\n";
                break;
            case 9:
                if (!saveAllData()) cout << "Warning: some data could not be saved.\n";
                cout << "Goodbye!\n";
                running = false;
                break;
        }
    }
}

bool SystemManager::saveAllData() {
    bool productsOk = productManager.saveToFile();
    bool restockOk = inventoryManager.saveRestockRequests();
    return productsOk && restockOk;   // sales.txt is appended at the moment of each sale
}

void SystemManager::clearUndoHistory(const std::string& reason) {
    if (undoStack.empty()) return;
    while (!undoStack.empty()) undoStack.pop();
    cout << "(Undo history cleared: " << reason << ")\n";
}

// ---------- Submenus (each performs one action, then returns to the main menu) ----------

void SystemManager::productMenu() {
    cout << "\n--- Product Management ---\n";
    cout << " 1. Add product\n 2. Display all products\n 3. Search product by ID\n";
    cout << " 4. Update product\n 5. Delete product\n 6. Back to main menu\n";
    int choice = Utils::readInt("Enter your choice (1-6): ", 1, 6);
    UndoRecord record;
    switch (choice) {
        case 1: {
            int id = productManager.addProductInteractive();
            if (id != 0) {
                Product* added = productManager.findProductById(id);
                record.type = UndoType::AddProduct;
                record.product = *added;
                record.product.next = nullptr;
                undoStack.push(record);
            }
            break;
        }
        case 2: productManager.displayAllProducts(); break;
        case 3: productManager.searchProductInteractive(); break;
        case 4:
            if (productManager.updateProductInteractive(record.product)) {
                record.type = UndoType::UpdateProduct;
                undoStack.push(record);
            }
            break;
        case 5:
            if (productManager.deleteProductInteractive(record.product)) {
                record.type = UndoType::DeleteProduct;
                undoStack.push(record);
            }
            break;
        default: break;
    }
}

void SystemManager::sellProduct() {
    UndoRecord record;
    if (salesManager.sellProductInteractive(record.sale)) {
        record.type = UndoType::SellProduct;
        undoStack.push(record);
    }
}

void SystemManager::inventoryMenu() {
    cout << "\n--- Inventory and Restocking ---\n";
    cout << " 1. Inventory status\n 2. Check low-stock products\n";
    cout << " 3. Create restock requests for low-stock products\n";
    cout << " 4. Receive next restock request (oldest first)\n 5. Back to main menu\n";
    int choice = Utils::readInt("Enter your choice (1-5): ", 1, 5);
    switch (choice) {
        case 1: inventoryManager.displayInventoryStatus(); break;
        case 2: inventoryManager.checkLowStock(); break;
        case 3: inventoryManager.createRestockRequests(); break;
        case 4:
            if (inventoryManager.fulfillNextRestockRequest()) {
                clearUndoHistory("received stock cannot be undone safely");
            }
            break;
        default: break;
    }
}

void SystemManager::expiryMenu() {
    cout << "\n--- Expiry and Discount Analysis ---\n";
    cout << " 1. Show expired / near-expiry products\n";
    cout << " 2. Apply discount to near-expiry products\n 3. Back to main menu\n";
    int choice = Utils::readInt("Enter your choice (1-3): ", 1, 3);
    if (choice == 3) return;

    cout << "Dates use the format YYYY-MM-DD.\n";
    std::string today = Utils::readDateOrToday("Enter today's date (or press Enter to use the system date): ");
    if (choice == 1) {
        inventoryManager.analyzeExpiry(today);
    } else {
        inventoryManager.analyzeExpiry(today);
        if (inventoryManager.applyNearExpiryDiscounts(today) > 0) {
            clearUndoHistory("discounts cannot be undone");
        }
    }
}

// ---------- Undo (stack) ----------

void SystemManager::undoLastOperation() {
    cout << "\n--- Undo Last Operation ---\n";
    if (undoStack.empty()) {
        cout << "Nothing to undo. (Supported: add, update, delete product and sell product.)\n";
        return;
    }
    UndoRecord record = undoStack.top();
    undoStack.pop();
    bool ok = false;
    switch (record.type) {
        case UndoType::AddProduct:
            ok = productManager.deleteProductById(record.product.id);
            if (ok) cout << "Undone: removed product '" << record.product.name << "'.\n";
            break;
        case UndoType::DeleteProduct:
            ok = productManager.insertProduct(record.product);
            if (ok) cout << "Undone: restored deleted product '" << record.product.name << "'.\n";
            break;
        case UndoType::UpdateProduct:
            ok = productManager.restoreProduct(record.product);
            if (ok) cout << "Undone: restored old values of product '" << record.product.name << "'.\n";
            break;
        case UndoType::SellProduct:
            ok = salesManager.undoSale(record.sale);
            if (ok) cout << "Undone: sale #" << record.sale.saleId << " reversed, "
                         << record.sale.quantity << " unit(s) returned to stock.\n";
            break;
    }
    if (!ok) {
        cout << "The operation could not be undone.\n";
        return;
    }
    if (record.type != UndoType::SellProduct && !productManager.saveToFile()) {
        cout << "Warning: products.txt could not be updated after the undo.\n";
    }
}
