// Declares functions related to sales management.
// SalesManager.h - Member 2: selling products, bills, sales history.
#pragma once
#include <vector>

#include "FileManager.h"
#include "Product.h"
#include "ProductManager.h"

class SalesManager {
public:
    SalesManager(ProductManager* productManager, FileManager* fileManager);

    bool loadHistory();
    bool sellProductInteractive(SaleRecord& completedSale);  // true only for a completed sale
    void displaySalesHistory() const;
    bool undoSale(const SaleRecord& sale);                   // used by SystemManager's undo
    int getSalesCount() const;

private:
    ProductManager* productManager;
    FileManager* fileManager;
    std::vector<SaleRecord> history;
    int nextSaleId;
};
