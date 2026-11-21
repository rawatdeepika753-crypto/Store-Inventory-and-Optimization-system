#include "FileManager.h"

#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

#include "Utils.h"

namespace {

std::string productsHeader() {
    return "# Store Inventory System - products.txt\n"
           "# Format: id|name|category|quantity|reorderLevel|price|discountedPrice|expiryDate\n"
           "# expiryDate is YYYY-MM-DD or NA. Lines starting with # are ignored.\n";
}

std::string salesHeader() {
    return "# Store Inventory System - sales.txt (completed sales only)\n"
           "# Format: saleId|dateTime|productId|productName|quantity|unitPrice|totalBill\n";
}

std::string restockHeader() {
    return "# Store Inventory System - restock.txt\n"
           "# Format: requestId|productId|productName|currentQty|requestedQty|dateRequested|status|dateClosed\n"
           "# status is PENDING, FULFILLED or CANCELLED. PENDING lines are kept in FIFO order.\n";
}

std::vector<std::string> splitLine(const std::string& line, char delimiter) {
    std::vector<std::string> parts;
    std::string current;
    std::stringstream stream(line);
    while (std::getline(stream, current, delimiter)) {
        parts.push_back(current);
    }
    return parts;
}

bool isSkippableLine(const std::string& line) {
    return line.empty() || line[0] == '#';
}

// Copies a file to <path>.bak so malformed lines are never silently lost.
void backupFile(const std::string& path) {
    std::ifstream in(path.c_str(), std::ios::binary);
    if (!in) return;
    std::string backupPath = path + ".bak";
    std::ofstream out(backupPath.c_str(), std::ios::binary);
    if (!out) return;
    out << in.rdbuf();
    std::cout << "  A backup of the original file was saved as " << backupPath << "\n";
}

// Windows cannot rename over an existing file, so remove the old file first.
bool replaceFile(const std::string& tempPath, const std::string& finalPath) {
    std::remove(finalPath.c_str());
    return std::rename(tempPath.c_str(), finalPath.c_str()) == 0;
}

bool parseProductLine(const std::string& line, Product& product) {
    std::vector<std::string> f = splitLine(line, '|');
    if (f.size() != 8) return false;
    if (!Utils::tryParseInt(f[0], product.id) || product.id <= 0) return false;
    product.name = f[1];
    product.category = f[2];
    if (product.name.empty() || product.category.empty()) return false;
    if (!Utils::tryParseInt(f[3], product.quantity) || product.quantity < 0) return false;
    if (!Utils::tryParseInt(f[4], product.reorderLevel) || product.reorderLevel < 0) return false;
    if (!Utils::tryParseDouble(f[5], product.price) || product.price <= 0) return false;
    if (!Utils::tryParseDouble(f[6], product.discountedPrice) || product.discountedPrice <= 0 ||
        product.discountedPrice > product.price + 0.005) return false;
    if (!Utils::isValidExpiryField(f[7])) return false;
    product.expiryDate = f[7];
    return true;
}

bool parseSaleLine(const std::string& line, SaleRecord& sale) {
    std::vector<std::string> f = splitLine(line, '|');
    if (f.size() != 7) return false;
    if (!Utils::tryParseInt(f[0], sale.saleId) || sale.saleId <= 0) return false;
    sale.dateTime = f[1];
    if (!Utils::tryParseInt(f[2], sale.productId) || sale.productId <= 0) return false;
    sale.productName = f[3];
    if (!Utils::tryParseInt(f[4], sale.quantity) || sale.quantity <= 0) return false;
    if (!Utils::tryParseDouble(f[5], sale.unitPrice) || sale.unitPrice < 0) return false;
    if (!Utils::tryParseDouble(f[6], sale.totalBill) || sale.totalBill < 0) return false;
    return !sale.dateTime.empty() && !sale.productName.empty();
}

bool parseRestockLine(const std::string& line, RestockRequest& request) {
    std::vector<std::string> f = splitLine(line, '|');
    if (f.size() != 8) return false;
    if (!Utils::tryParseInt(f[0], request.requestId) || request.requestId <= 0) return false;
    if (!Utils::tryParseInt(f[1], request.productId) || request.productId <= 0) return false;
    request.productName = f[2];
    if (!Utils::tryParseInt(f[3], request.currentQuantity) || request.currentQuantity < 0) return false;
    if (!Utils::tryParseInt(f[4], request.requestedQuantity) || request.requestedQuantity <= 0) return false;
    request.dateRequested = f[5];
    request.status = f[6];
    request.dateClosed = f[7];
    if (request.status != "PENDING" && request.status != "FULFILLED" && request.status != "CANCELLED") {
        return false;
    }
    return !request.productName.empty() && !request.dateRequested.empty();
}

void writeSaleLine(std::ostream& out, const SaleRecord& s) {
    out << s.saleId << '|' << s.dateTime << '|' << s.productId << '|' << s.productName << '|'
        << s.quantity << '|' << Utils::formatMoney(s.unitPrice) << '|'
        << Utils::formatMoney(s.totalBill) << '\n';
}

void writeRestockLine(std::ostream& out, const RestockRequest& r) {
    out << r.requestId << '|' << r.productId << '|' << r.productName << '|' << r.currentQuantity
        << '|' << r.requestedQuantity << '|' << r.dateRequested << '|' << r.status << '|'
        << r.dateClosed << '\n';
}

}  // namespace

FileManager::FileManager(const std::string& dataFolder) {
    std::string folder = dataFolder;
    while (!folder.empty() && (folder.back() == '/' || folder.back() == '\\')) {
        folder.pop_back();
    }
    std::string prefix = (folder.empty() || folder == ".") ? "" : folder + "/";
    productsPath = prefix + "products.txt";
    salesPath = prefix + "sales.txt";
    restockPath = prefix + "restock.txt";
}

bool FileManager::createFileIfMissing(const std::string& path, const std::string& header) const {
    std::ifstream existing(path.c_str());
    if (existing) return true;  // already there: never overwrite
    std::ofstream created(path.c_str());
    if (!created) {
        std::cout << "Error: cannot create " << path << ". Check that the folder exists and is writable.\n";
        return false;
    }
    created << header;
    std::cout << "  Created missing data file: " << path << "\n";
    return true;
}

bool FileManager::initializeFiles() const {
    return createFileIfMissing(productsPath, productsHeader()) &&
           createFileIfMissing(salesPath, salesHeader()) &&
           createFileIfMissing(restockPath, restockHeader());
}

bool FileManager::loadProductsFromFile(Product*& head, int& skippedLines) const {
    skippedLines = 0;
    std::ifstream in(productsPath.c_str());
    if (!in) {
        std::cout << "Error: cannot open " << productsPath << " for reading.\n";
        return false;
    }
    Product* tail = nullptr;
    for (Product* c = head; c != nullptr; c = c->next) tail = c;

    std::string line;
    int lineNumber = 0;
    while (std::getline(in, line)) {
        ++lineNumber;
        line = Utils::trim(line);
        if (isSkippableLine(line)) continue;

        Product product;
        if (!parseProductLine(line, product)) {
            std::cout << "  Warning: products.txt line " << lineNumber << " is malformed and was skipped.\n";
            ++skippedLines;
            continue;
        }
        bool duplicate = false;
        for (Product* c = head; c != nullptr; c = c->next) {
            if (c->id == product.id) { duplicate = true; break; }
        }
        if (duplicate) {
            std::cout << "  Warning: products.txt line " << lineNumber << " repeats product ID "
                      << product.id << " and was skipped.\n";
            ++skippedLines;
            continue;
        }
        Product* node = new Product(product);
        node->next = nullptr;
        if (head == nullptr) head = node; else tail->next = node;
        tail = node;
    }
    in.close();
    if (skippedLines > 0) backupFile(productsPath);
    return true;
}

bool FileManager::saveProductsToFile(const Product* head) const {
    std::string tempPath = productsPath + ".tmp";
    std::ofstream out(tempPath.c_str());
    if (!out) {
        std::cout << "Error: cannot write " << tempPath << ". Data was NOT saved.\n";
        return false;
    }
    out << productsHeader();
    for (const Product* c = head; c != nullptr; c = c->next) {
        out << c->id << '|' << c->name << '|' << c->category << '|' << c->quantity << '|'
            << c->reorderLevel << '|' << Utils::formatMoney(c->price) << '|'
            << Utils::formatMoney(c->discountedPrice) << '|' << c->expiryDate << '\n';
    }
    out.close();
    if (out.fail()) {
        std::cout << "Error: writing " << tempPath << " failed. Existing products.txt was kept.\n";
        std::remove(tempPath.c_str());
        return false;
    }
    if (!replaceFile(tempPath, productsPath)) {
        std::cout << "Error: could not replace " << productsPath << ". New data is in " << tempPath << ".\n";
        return false;
    }
    return true;
}

bool FileManager::loadSalesFromFile(std::vector<SaleRecord>& sales, int& skippedLines) const {
    skippedLines = 0;
    std::ifstream in(salesPath.c_str());
    if (!in) {
        std::cout << "Error: cannot open " << salesPath << " for reading.\n";
        return false;
    }
    std::string line;
    int lineNumber = 0;
    while (std::getline(in, line)) {
        ++lineNumber;
        line = Utils::trim(line);
        if (isSkippableLine(line)) continue;
        SaleRecord sale;
        if (!parseSaleLine(line, sale)) {
            std::cout << "  Warning: sales.txt line " << lineNumber << " is malformed and was skipped.\n";
            ++skippedLines;
            continue;
        }
        sales.push_back(sale);
    }
    in.close();
    if (skippedLines > 0) backupFile(salesPath);
    return true;
}

bool FileManager::saveSalesToFile(const SaleRecord& sale) const {
    std::ofstream out(salesPath.c_str(), std::ios::app);
    if (!out) {
        std::cout << "Error: cannot open " << salesPath << " for appending.\n";
        return false;
    }
    writeSaleLine(out, sale);
    out.close();
    return !out.fail();
}

bool FileManager::saveAllSalesToFile(const std::vector<SaleRecord>& sales) const {
    std::string tempPath = salesPath + ".tmp";
    std::ofstream out(tempPath.c_str());
    if (!out) {
        std::cout << "Error: cannot write " << tempPath << ".\n";
        return false;
    }
    out << salesHeader();
    for (std::size_t i = 0; i < sales.size(); ++i) writeSaleLine(out, sales[i]);
    out.close();
    if (out.fail()) {
        std::remove(tempPath.c_str());
        return false;
    }
    return replaceFile(tempPath, salesPath);
}

bool FileManager::loadRestockFromFile(std::queue<RestockRequest>& pending,
                                      std::vector<RestockRequest>& closedRequests,
                                      int& skippedLines) const {
    skippedLines = 0;
    std::ifstream in(restockPath.c_str());
    if (!in) {
        std::cout << "Error: cannot open " << restockPath << " for reading.\n";
        return false;
    }
    std::string line;
    int lineNumber = 0;
    while (std::getline(in, line)) {
        ++lineNumber;
        line = Utils::trim(line);
        if (isSkippableLine(line)) continue;
        RestockRequest request;
        if (!parseRestockLine(line, request)) {
            std::cout << "  Warning: restock.txt line " << lineNumber << " is malformed and was skipped.\n";
            ++skippedLines;
            continue;
        }
        if (request.status == "PENDING") pending.push(request);   // file order = FIFO order
        else closedRequests.push_back(request);
    }
    in.close();
    if (skippedLines > 0) backupFile(restockPath);
    return true;
}

bool FileManager::saveRestockToFile(const std::queue<RestockRequest>& pending,
                                    const std::vector<RestockRequest>& closedRequests) const {
    std::string tempPath = restockPath + ".tmp";
    std::ofstream out(tempPath.c_str());
    if (!out) {
        std::cout << "Error: cannot write " << tempPath << ". Restock data was NOT saved.\n";
        return false;
    }
    out << restockHeader();
    for (std::size_t i = 0; i < closedRequests.size(); ++i) writeRestockLine(out, closedRequests[i]);
    std::queue<RestockRequest> copy = pending;   // copy so the real queue stays untouched
    while (!copy.empty()) {
        writeRestockLine(out, copy.front());
        copy.pop();
    }
    out.close();
    if (out.fail()) {
        std::remove(tempPath.c_str());
        return false;
    }
    return replaceFile(tempPath, restockPath);
}
