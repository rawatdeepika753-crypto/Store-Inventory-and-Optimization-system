<<<<<<< HEAD
=======
//Handles all the product management operations 
>>>>>>> rebuild-contributions
// Product.h - shared data model used by ALL modules.
// Product      : one node of the singly linked list (the shared in-memory collection).
// SaleRecord   : one completed sale (stored in sales.txt).
// RestockRequest: one restock request (stored in restock.txt, queued in memory).
#pragma once
#include <string>

struct Product {
    int id = 0;
    std::string name;
    std::string category;
    int quantity = 0;
    int reorderLevel = 0;
    double price = 0.0;
    double discountedPrice = 0.0;        // equals price when no discount is active
    std::string expiryDate = "NA";       // "YYYY-MM-DD" or "NA" (does not expire)
    Product* next = nullptr;             // next node in the singly linked list
};

struct SaleRecord {
    int saleId = 0;
    std::string dateTime;                // "YYYY-MM-DD HH:MM:SS" (system clock)
    int productId = 0;
    std::string productName;
    int quantity = 0;
    double unitPrice = 0.0;
    double totalBill = 0.0;
};

struct RestockRequest {
    int requestId = 0;
    int productId = 0;
    std::string productName;
    int currentQuantity = 0;             // stock level when the request was created
    int requestedQuantity = 0;           // targetStock - currentQuantity
    std::string dateRequested;           // YYYY-MM-DD
    std::string status = "PENDING";      // PENDING, FULFILLED or CANCELLED
    std::string dateClosed = "-";        // "-" while pending
};
