#include <iostream>
#include <sstream>
#include <string>
#include "access_control_system.h"


void showWelcomeScreen() {
    std::cout << "Graph-Based Access Control System Command Format:\n";
    std::cout << "  addUser <userID>\n";
    std::cout << "  addGroup <groupID>\n";
    std::cout << "  addResource <resourceID>\n";
    std::cout << "  addPermission <permissionID>\n";
    std::cout << "  addUserToGroup <userID> <groupID>\n";
    std::cout << "  grantPermissionToGroup <permissionID> <groupID>\n";
    std::cout << "  applyPermissionToResource <permissionID> <resourceID>\n";
    std::cout << "  hasAccess <userID> <permissionID> <resourceID>\n";
    std::cout << "Only hasAccess produces output (true/false). Ctrl+D (EOF) to exit.\n";
    std::cout << "showGraph or printState for viewing the table. Ctrl+D (EOF) to exit.\n";
    std::cout << "-------------------------------------------------------------\n";
}

int main() {
    showWelcomeScreen();
    AccessControlSystem acs;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream iss(line);
        std::string cmd;
        iss >> cmd;
        if (cmd == "addUser") {
            std::string userID; iss >> userID;
            acs.addUser(userID);
        } else if (cmd == "addGroup") {
            std::string groupID; iss >> groupID;
            acs.addGroup(groupID);
        } else if (cmd == "addResource") {
            std::string resourceID; iss >> resourceID;
            acs.addResource(resourceID);
        } else if (cmd == "addPermission") {
            std::string permID; iss >> permID;
            acs.addPermission(permID);
        } else if (cmd == "addUserToGroup") {
            std::string userID, groupID; iss >> userID >> groupID;
            acs.addUserToGroup(userID, groupID);
        } else if (cmd == "grantPermissionToGroup") {
            std::string permID, groupID; iss >> permID >> groupID;
            acs.grantPermissionToGroup(permID, groupID);
        } else if (cmd == "applyPermissionToResource") {
            std::string permID, resID; iss >> permID >> resID;
            acs.applyPermissionToResource(permID, resID);
        } else if (cmd == "hasAccess") {
            std::string userID, permID, resID; iss >> userID >> permID >> resID;
            std::cout << (acs.hasAccess(userID, permID, resID) ? "true" : "false") << std::endl;
        }
		else if (cmd == "showGraph" || cmd == "printState") {
			acs.printState();
		}


    }
    return 0;
}
