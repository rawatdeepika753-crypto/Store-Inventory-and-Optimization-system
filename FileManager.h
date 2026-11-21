// FileManager.h - ALL file reading/writing lives here (centralised persistence).
#pragma once
#include <queue>
#include <string>
#include <vector>

#include "Product.h"

class FileManager {
public:
    // dataFolder: folder that contains products.txt, sales.txt and restock.txt.
    explicit FileManager(const std::string& dataFolder = ".");

    // Creates any missing data file (with a comment header). Never overwrites existing files.
    bool initializeFiles() const;

    // products.txt -> builds the linked list (head must be nullptr). Malformed lines are skipped.
    bool loadProductsFromFile(Product*& head, int& skippedLines) const;
    bool saveProductsToFile(const Product* head) const;

    // sales.txt: history is appended one record at a time; rewritten only by undo.
    bool loadSalesFromFile(std::vector<SaleRecord>& sales, int& skippedLines) const;
    bool saveSalesToFile(const SaleRecord& sale) const;               // append
    bool saveAllSalesToFile(const std::vector<SaleRecord>& sales) const; // rewrite (undo)

    // restock.txt: pending requests (FIFO order) + closed requests (history).
    bool loadRestockFromFile(std::queue<RestockRequest>& pending,
                             std::vector<RestockRequest>& closedRequests,
                             int& skippedLines) const;
    bool saveRestockToFile(const std::queue<RestockRequest>& pending,
                           const std::vector<RestockRequest>& closedRequests) const;

private:
    std::string productsPath;
    std::string salesPath;
    std::string restockPath;

    bool createFileIfMissing(const std::string& path, const std::string& header) const;
};
