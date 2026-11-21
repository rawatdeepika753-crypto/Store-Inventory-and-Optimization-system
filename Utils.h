@@ -0,0 +1,37 @@
// Utils.h - small helpers shared by all modules: safe console input and date handling.
// (Extra file beyond the required list; it avoids duplicating input/date code in every module.)
#pragma once
#include <cstddef>
#include <string>

namespace Utils {

// Thrown when the input stream is closed (Ctrl+Z / end of piped input).
struct InputClosed {};

std::string trim(const std::string& text);
std::string truncate(const std::string& text, std::size_t width);
std::string formatMoney(double value);
double roundMoney(double value);

bool tryParseInt(const std::string& text, int& result);
bool tryParseDouble(const std::string& text, double& result);

// Input helpers: they keep asking until the input is valid.
// If keepValue is given, pressing Enter keeps that current value.
std::string readLine(const std::string& prompt);
int readInt(const std::string& prompt, int minValue, int maxValue, const int* keepValue = nullptr);
double readDouble(const std::string& prompt, double minValue, const double* keepValue = nullptr);
std::string readText(const std::string& prompt, const std::string* keepValue = nullptr);
std::string readExpiryDate(const std::string& prompt, const std::string* keepValue = nullptr);
std::string readDateOrToday(const std::string& prompt);   // blank input = system date
bool readYesNo(const std::string& prompt);

// Dates use the format YYYY-MM-DD, years 1900-2100.
bool isValidDate(const std::string& date);
bool isValidExpiryField(const std::string& text);          // valid date or "NA"
int daysBetween(const std::string& fromDate, const std::string& toDate); // toDate - fromDate
std::string getSystemDate();
std::string getSystemDateTime();

}  // namespace Utils
