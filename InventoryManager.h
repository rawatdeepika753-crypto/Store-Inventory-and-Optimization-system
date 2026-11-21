// InventoryManager.h - Member 3: low stock, restock queue, expiry analysis and discounts.
#pragma once
#include <queue>
#include <string>
#include <vector>

#include "FileManager.h"
#include "Product.h"
#include "ProductManager.h"

class InventoryManager {
public:
    // Business rules (documented in README):
    static constexpr int TARGET_STOCK_MULTIPLIER = 2;  // target stock = 2 x reorder level
    static constexpr int NEAR_EXPIRY_DAYS = 7;         // 0..7 days left = near expiry
    static constexpr int DISCOUNT_PERCENT = 20;        // discount for near-expiry products

    InventoryManager(ProductManager* productManager, FileManager* fileManager);

    bool loadRestockRequests();
    bool saveRestockRequests() const;
    int getPendingCount() const;

    void displayInventoryStatus() const;
    int checkLowStock() const;                 // prints low-stock products, returns how many
    int createRestockRequests();               // queues requests for low-stock products
    void displayRestockRequests() const;       // pending queue + history
    bool fulfillNextRestockRequest();          // dequeues oldest request; true if stock changed

    void analyzeExpiry(const std::string& today) const;
    int applyNearExpiryDiscounts(const std::string& today);   // returns number discounted

    static int calculateTargetStock(const Product& product);

private:
    ProductManager* productManager;
    FileManager* fileManager;
    std::queue<RestockRequest> pendingRequests;      // FIFO queue
    std::vector<RestockRequest> closedRequests;      // fulfilled / cancelled history
    int nextRequestId;

    bool hasPendingRequest(int productId) const;
};
