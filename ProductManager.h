// ProductManager.h - Member 1: product management on a singly linked list + binary-search index.
#pragma once
#include <vector>

#include "FileManager.h"
#include "Product.h"

class ProductManager {
public:
    static constexpr int MAX_PRODUCT_ID = 999999;
    static constexpr int MAX_QUANTITY = 1000000;

    explicit ProductManager(FileManager* fileManager);
    ~ProductManager();
    ProductManager(const ProductManager&) = delete;
    ProductManager& operator=(const ProductManager&) = delete;

    // File storage
    bool loadFromFile();
    bool saveToFile() const;

    // Menu operations (they read user input, change the list and save products.txt)
    int addProductInteractive();                       // returns new ID, or 0 if nothing was added
    void displayAllProducts() const;
    void searchProductInteractive();
    bool updateProductInteractive(Product& beforeChange);   // beforeChange = copy of old values
    bool deleteProductInteractive(Product& deletedCopy);    // deletedCopy   = copy of removed product

    // Core operations used by other modules (no user input, no saving)
    bool insertProduct(const Product& product);        // appends a new node at the tail
    bool deleteProductById(int id);
    bool restoreProduct(const Product& snapshot);      // overwrite fields of the node with snapshot.id
    Product* findProductById(int id);                  // binary search; nullptr if missing
    Product* getHead() const;
    int getProductCount() const;

private:
    struct IndexEntry {
        int id;
        Product* node;
    };

    FileManager* fileManager;
    Product* head;
    int productCount;
    std::vector<IndexEntry> searchIndex;   // sorted by id; rebuilt lazily
    bool indexValid;

    void rebuildSearchIndex();
    void invalidateIndex();
    void clearList();
};
