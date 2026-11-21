@@ -0,0 +1,219 @@
#include "Utils.h"

#include <cctype>
#include <cmath>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace Utils {

namespace {

bool isLeapYear(int year) {
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

int daysInMonth(int year, int month) {
    static const int days[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (month == 2 && isLeapYear(year)) {
        return 29;
    }
    return days[month - 1];
}

bool parseDateParts(const std::string& date, int& year, int& month, int& day) {
    if (date.size() != 10 || date[4] != '-' || date[7] != '-') {
        return false;
    }
    for (std::size_t i = 0; i < date.size(); ++i) {
        if (i == 4 || i == 7) continue;
        if (!std::isdigit(static_cast<unsigned char>(date[i]))) return false;
    }
    year = std::stoi(date.substr(0, 4));
    month = std::stoi(date.substr(5, 2));
    day = std::stoi(date.substr(8, 2));
    if (year < 1900 || year > 2100) return false;
    if (month < 1 || month > 12) return false;
    if (day < 1 || day > daysInMonth(year, month)) return false;
    return true;
}

// Number of days from 1900-01-01 to the given (valid) date.
long dayNumber(int year, int month, int day) {
    long days = 0;
    for (int y = 1900; y < year; ++y) {
        days += isLeapYear(y) ? 366 : 365;
    }
    for (int m = 1; m < month; ++m) {
        days += daysInMonth(year, m);
    }
    return days + day;
}

std::string toUpper(std::string text) {
    for (std::size_t i = 0; i < text.size(); ++i) {
        text[i] = static_cast<char>(std::toupper(static_cast<unsigned char>(text[i])));
    }
    return text;
}

std::string formatTime(const char* format) {
    std::time_t now = std::time(nullptr);
    std::tm* local = std::localtime(&now);
    char buffer[32];
    std::strftime(buffer, sizeof(buffer), format, local);
    return std::string(buffer);
}

}  // namespace

std::string trim(const std::string& text) {
    std::size_t start = 0;
    while (start < text.size() && std::isspace(static_cast<unsigned char>(text[start]))) ++start;
    std::size_t end = text.size();
    while (end > start && std::isspace(static_cast<unsigned char>(text[end - 1]))) --end;
    return text.substr(start, end - start);
}

std::string truncate(const std::string& text, std::size_t width) {
    if (text.size() <= width) return text;
    if (width < 3) return text.substr(0, width);
    return text.substr(0, width - 2) + "..";
}

std::string formatMoney(double value) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(2) << value;
    return out.str();
}

double roundMoney(double value) {
    return std::floor(value * 100.0 + 0.5) / 100.0;
}

bool tryParseInt(const std::string& text, int& result) {
    try {
        std::size_t pos = 0;
        int value = std::stoi(text, &pos);
        if (pos != text.size()) return false;
        result = value;
        return true;
    } catch (...) {
        return false;
    }
}

bool tryParseDouble(const std::string& text, double& result) {
    try {
        std::size_t pos = 0;
        double value = std::stod(text, &pos);
        if (pos != text.size() || !std::isfinite(value)) return false;
        result = value;
        return true;
    } catch (...) {
        return false;
    }
}

std::string readLine(const std::string& prompt) {
    std::cout << prompt;
    std::string line;
    if (!std::getline(std::cin, line)) {
        throw InputClosed();
    }
    return trim(line);
}

int readInt(const std::string& prompt, int minValue, int maxValue, const int* keepValue) {
    while (true) {
        std::string text = readLine(prompt);
        if (text.empty() && keepValue != nullptr) return *keepValue;
        int value = 0;
        if (tryParseInt(text, value) && value >= minValue && value <= maxValue) return value;
        std::cout << "  Invalid input. Please enter a whole number between " << minValue
                  << " and " << maxValue << ".\n";
    }
}

double readDouble(const std::string& prompt, double minValue, const double* keepValue) {
    while (true) {
        std::string text = readLine(prompt);
        if (text.empty() && keepValue != nullptr) return *keepValue;
        double value = 0.0;
        if (tryParseDouble(text, value) && value >= minValue && value <= 100000000.0) return value;
        std::cout << "  Invalid input. Please enter a number of at least " << minValue << ".\n";
    }
}

std::string readText(const std::string& prompt, const std::string* keepValue) {
    while (true) {
        std::string text = readLine(prompt);
        if (text.empty() && keepValue != nullptr) return *keepValue;
        if (text.empty()) {
            std::cout << "  This field cannot be empty.\n";
        } else if (text.find('|') != std::string::npos) {
            std::cout << "  The '|' character is not allowed (it separates fields in the data files).\n";
        } else if (text.size() > 40) {
            std::cout << "  Please use at most 40 characters.\n";
        } else {
            return text;
        }
    }
}

std::string readExpiryDate(const std::string& prompt, const std::string* keepValue) {
    while (true) {
        std::string text = readLine(prompt);
        if (text.empty() && keepValue != nullptr) return *keepValue;
        if (toUpper(text) == "NA") return "NA";
        if (isValidDate(text)) return text;
        std::cout << "  Invalid date. Use a real calendar date as YYYY-MM-DD (e.g. 2026-12-31) or NA.\n";
    }
}

std::string readDateOrToday(const std::string& prompt) {
    while (true) {
        std::string text = readLine(prompt);
        if (text.empty()) return getSystemDate();
        if (isValidDate(text)) return text;
        std::cout << "  Invalid date. Use a real calendar date as YYYY-MM-DD, or press Enter for the system date.\n";
    }
}

bool readYesNo(const std::string& prompt) {
    while (true) {
        std::string text = toUpper(readLine(prompt));
        if (text == "Y" || text == "YES") return true;
        if (text == "N" || text == "NO") return false;
        std::cout << "  Please answer y or n.\n";
    }
}

bool isValidDate(const std::string& date) {
    int y = 0, m = 0, d = 0;
    return parseDateParts(date, y, m, d);
}

bool isValidExpiryField(const std::string& text) {
    return text == "NA" || isValidDate(text);
}

int daysBetween(const std::string& fromDate, const std::string& toDate) {
    int y1 = 0, m1 = 0, d1 = 0, y2 = 0, m2 = 0, d2 = 0;
    if (!parseDateParts(fromDate, y1, m1, d1) || !parseDateParts(toDate, y2, m2, d2)) {
        return 0;
    }
    return static_cast<int>(dayNumber(y2, m2, d2) - dayNumber(y1, m1, d1));
}

std::string getSystemDate() {
    return formatTime("%Y-%m-%d");
}

std::string getSystemDateTime() {
    return formatTime("%Y-%m-%d %H:%M:%S");
}

}  // namespace Utils
