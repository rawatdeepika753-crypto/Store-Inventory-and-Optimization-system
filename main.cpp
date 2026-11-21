@@ -0,0 +1,22 @@
// main.cpp - entry point. Flow: main -> SystemManager -> Product/Sales/Inventory -> FileManager -> text files.
// Optional argument: folder that holds products.txt, sales.txt and restock.txt (default: current folder).
#include <iostream>
#include <string>

#include "SystemManager.h"
#include "Utils.h"

int main(int argc, char* argv[]) {
    std::string dataFolder = (argc > 1) ? argv[1] : ".";
    try {
        SystemManager system(dataFolder);
        if (!system.initialize()) {
            std::cout << "Startup failed. Check that the data folder exists and the files are readable.\n";
            return 1;
        }
        system.run();
    } catch (const Utils::InputClosed&) {
        std::cout << "\nInput closed. Exiting (data was saved after each change).\n";
    }
    return 0;
}
