#pragma once
#include <unordered_map>
#include <vector>
#include <queue>
#include <string>


enum class NodeType { User, Group, Permission, Resource };


class AccessControlSystem {
public:
    struct Node {
        std::string id;
        NodeType type;
        Node(const std::string &i, NodeType t) : id(i), type(t) {}
    };

    std::unordered_map<std::string, int> idToIndex;
    std::vector<Node> nodes;
    std::vector<std::vector<int>> edges;

    AccessControlSystem() {}

    void addEntity(const std::string &id, NodeType type) {
        if (idToIndex.count(id)) return;
        int idx = nodes.size();
        nodes.push_back(Node{id, type});
        edges.push_back({});
        idToIndex[id] = idx;
    }
    void addUser(const std::string &userID)       { addEntity(userID, NodeType::User); }
    void addGroup(const std::string &groupID)     { addEntity(groupID, NodeType::Group); }
    void addPermission(const std::string &permID) { addEntity(permID, NodeType::Permission); }
    void addResource(const std::string &resID)    { addEntity(resID, NodeType::Resource); }

    void addUserToGroup(const std::string &userID, const std::string &groupID) {
        if (!idToIndex.count(userID) || !idToIndex.count(groupID)) return;
        edges[idToIndex[userID]].push_back(idToIndex[groupID]);
    }
    void grantPermissionToGroup(const std::string &permissionID, const std::string &groupID) {
        if (!idToIndex.count(groupID) || !idToIndex.count(permissionID)) return;
        edges[idToIndex[groupID]].push_back(idToIndex[permissionID]);
    }
    void applyPermissionToResource(const std::string &permissionID, const std::string &resourceID) {
        if (!idToIndex.count(resourceID) || !idToIndex.count(permissionID)) return;
        edges[idToIndex[permissionID]].push_back(idToIndex[resourceID]);
    }

    bool hasAccess(const std::string &userID, const std::string &permissionID, const std::string &resourceID) {
        if (!idToIndex.count(userID) || !idToIndex.count(permissionID) || !idToIndex.count(resourceID)) return false;
        int start = idToIndex[userID], perm = idToIndex[permissionID], res = idToIndex[resourceID];
        std::queue<std::pair<int,int>> bfsQ; 
        std::vector<std::vector<bool>> visited(nodes.size(), std::vector<bool>(2, false));
        bfsQ.push({start, 0}); visited[start][0] = true;
        while (!bfsQ.empty()) {
            auto [curr, seenPerm] = bfsQ.front(); bfsQ.pop();
            if (curr == res && seenPerm == 1) return true;
            for (int nei : edges[curr]) {
                int nextSeenPerm = seenPerm; 
                if (nei == perm) nextSeenPerm = 1;
                if (!visited[nei][nextSeenPerm]) {
                    visited[nei][nextSeenPerm] = true;
                    bfsQ.push({nei, nextSeenPerm});
                }
            }
        }
        return false;
    }
	
	void printState() {
    std::cout << "ENTITY NODES:\n";
    for (size_t i = 0; i < nodes.size(); ++i) {
        std::cout << i << ": " << nodes[i].id << " [";
        switch (nodes[i].type) {
          case NodeType::User: std::cout << "User"; break;
          case NodeType::Group: std::cout << "Group"; break;
          case NodeType::Permission: std::cout << "Permission"; break;
          case NodeType::Resource: std::cout << "Resource"; break;
        }
        std::cout << "]\n";
    }
    std::cout << "EDGES (from->to):\n";
    for (size_t i = 0; i < edges.size(); ++i) {
        for (int j : edges[i]) {
            std::cout << nodes[i].id << " -> " << nodes[j].id << "\n";
        }
    }
    std::cout << "--------------------------\n";
}

};
