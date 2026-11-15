// SystemManager.h - Member 4: integration, menus, shared load/save and undo (stack).
#pragma once
#include <stack>
#include <string>

#include "FileManager.h"
#include "InventoryManager.h"
#include "Product.h"
#include "ProductManager.h"
#include "SalesManager.h"

// Undo is supported for: add product, delete product, update product, sell product.
enum class UndoType { AddProduct, DeleteProduct, UpdateProduct, SellProduct };

struct UndoRecord {
    UndoType type = UndoType::AddProduct;
    Product product;     // snapshot: the added product, deleted product or the OLD values
    SaleRecord sale;     // used by SellProduct
};

class SystemManager {
public:
    explicit SystemManager(const std::string& dataFolder);

    bool initialize();   // creates missing files, loads products, sales and restock data
    void run();          // main menu loop

private:
    // Declaration order matters: later members receive pointers to earlier ones.
    FileManager fileManager;
    ProductManager productManager;
    SalesManager salesManager;
    InventoryManager inventoryManager;
    std::stack<UndoRecord> undoStack;

    void showMainMenu() const;
    void productMenu();
    void inventoryMenu();
    void expiryMenu();
    void sellProduct();
    void undoLastOperation();
    bool saveAllData();
    void clearUndoHistory(const std::string& reason);
};
