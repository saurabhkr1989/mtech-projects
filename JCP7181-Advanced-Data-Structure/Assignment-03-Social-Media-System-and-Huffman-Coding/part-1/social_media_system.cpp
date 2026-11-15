/**
 * @file 2025JCS3011_1.cpp
 * @brief Backend for a simple Social Media System
 *
 * This program implements the backend logic for a social media platform. It handles user creation, connections (follow/unfollow), posts, and reactions. It reads commands from "input.txt" and writes results to "output.txt". The core of the system is designed using hash maps for quick data retrieval and a graph representation for the social network connections.
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <queue>
#include <algorithm>
#include <functional> // Required for std::function

// --- Data Structures ---

/**
 * @struct User
 * @brief Represents a user profile in the social media system.
 *
 * Stores all the necessary information for a single user.
 */
struct User {
    int profileId;
    std::string profileName;
    std::string email;
    bool isVerified;
};

/**
 * @struct Post
 * @brief Represents a single post made by a user.
 *
 * Stores the post's unique ID, the ID of the user who created it,
 * and a counter for reactions (likes/dislikes).
 */
struct Post {
    int postId;
    int userId;
    int count = 0; // A new post starts with a count of 0.
};

// --- Main System Class ---

/**
 * @class SocialMediaSystem
 * @brief Manages all users, posts, and their interactions.
 *
 * This class acts as the central hub for the entire application. It holds
 * the data and implements the logic for all the commands specified in the
 * assignment.
 */
class SocialMediaSystem {
private:
    // Using unordered_map for efficient O(1) average time complexity for lookups.
    std::unordered_map<int, User> users;
    std::unordered_map<int, Post> posts;
    // Adjacency list to represent the social graph (user connections).
    // A user ID maps to a set of their friends' IDs.
    std::unordered_map<int, std::unordered_set<int>> connections;

public:
    /**
     * @brief Creates a new user.
     * @param userId The unique ID for the new user.
     * @param name The profile name.
     * @param email The user's email.
     * @param isVerified Verification status.
     * @return True on success, false if the user ID already exists.
     */
    bool createUser(int userId, const std::string& name, const std::string& email, bool isVerified) {
        // Edge case: Check for uniqueness.
        if (users.count(userId)) {
            return false;
        }
        users[userId] = {userId, name, email, isVerified};
        return true;
    }

    /**
     * @brief Creates a mutual connection (undirected edge) between two users.
     * @param followerId The ID of the first user.
     * @param followedId The ID of the second user.
     * @return True on success, false on failure (e.g., users don't exist, connection exists).
     */
    bool follow(int followerId, int followedId) {
        // Edge cases:
        // 1. A user cannot follow themself.
        // 2. Both users must exist.
        // 3. The connection must not already exist.
        if (followerId == followedId || !users.count(followerId) || !users.count(followedId)) {
            return false;
        }
        if (connections.count(followerId) && connections[followerId].count(followedId)) {
            return false; // Already following
        }

        // Create the mutual connection.
        connections[followerId].insert(followedId);
        connections[followedId].insert(followerId);
        return true;
    }

    /**
     * @brief Removes a mutual connection between two users.
     * @param followerId The ID of the first user.
     * @param followedId The ID of the second user.
     * @return True on success, false if the connection doesn't exist.
     */
    bool unfollow(int followerId, int followedId) {
        // Edge case: Connection must exist to be removed.
        if (!connections.count(followerId) || !connections[followerId].count(followedId)) {
            return false;
        }
        connections[followerId].erase(followedId);
        connections[followedId].erase(followerId);
        return true;
    }

    /**
     * @brief Creates a new post.
     * @param postId The unique ID for the new post.
     * @param userId The ID of the user creating the post.
     * @return True on success, false if post ID exists or user doesn't exist.
     */
    bool createPost(int postId, int userId) {
        // Edge cases: Post ID must be unique, and the user must exist.
        if (posts.count(postId) || !users.count(userId)) {
            return false;
        }
        posts[postId] = {postId, userId, 0};
        return true;
    }

    /**
     * @brief Increments a post's reaction counter.
     * @param postId The ID of the post to like.
     * @return True on success, false if the post doesn't exist.
     */
    bool like(int postId) {
        if (!posts.count(postId)) {
            return false;
        }
        posts[postId].count++;
        return true;
    }

    /**
     * @brief Decrements a post's reaction counter.
     * @param postId The ID of the post to dislike.
     * @return True on success, false if the post doesn't exist.
     */
    bool dislike(int postId) {
        if (!posts.count(postId)) {
            return false;
        }
        posts[postId].count--;
        return true;
    }
    
    /**
     * @brief Retrieves the details of a specific user.
     * @param userId The ID of the user to look up.
     * @return A formatted string with user details, or "false" if user not found.
     */
    std::string getUserDetails(int userId) {
        if (!users.count(userId)) {
            return "false";
        }
        const auto& user = users[userId];
        return std::to_string(user.profileId) + " " + user.profileName + " " + user.email + " " + (user.isVerified ? "true" : "false");
    }

    /**
     * @brief Finds the top 'k' posts sorted by their reaction count.
     * @param k The number of top posts to return.
     * @return A space-separated string of the top posts in "userId-postId" format.
     */
    std::string topPosts(int k) {
        std::vector<Post> allPosts;
        for (const auto& pair : posts) {
            allPosts.push_back(pair.second);
        }

        // Sort posts in descending order of their count.
        // Sort posts in descending order of their count. The problem statement doesn't
        // specify a tie-break, so ties are broken by postId ascending for a deterministic,
        // reproducible result (std::sort alone is not guaranteed stable across runs/compilers).
        std::sort(allPosts.begin(), allPosts.end(), [](const Post& a, const Post& b) {
            if (a.count != b.count) return a.count > b.count;
            return a.postId < b.postId;
        });

        std::string result = "";
        for (int i = 0; i < k && i < allPosts.size(); ++i) {
            result += std::to_string(allPosts[i].userId) + "-" + std::to_string(allPosts[i].postId);
            if (i < k - 1 && i < allPosts.size() - 1) {
                result += " ";
            }
        }
        return result;
    }

    /**
     * @brief Finds the shortest connection path between two users using BFS.
     * @param userId1 The starting user ID.
     * @param userId2 The target user ID.
     * @return A space-separated string of user IDs in the path, or "-" if no path exists.
     */
    std::string followPath(int userId1, int userId2) {
        if (!users.count(userId1) || !users.count(userId2)) {
            return "-";
        }
        if (userId1 == userId2) {
            return std::to_string(userId1);
        }

        std::queue<int> q;
        q.push(userId1);
        
        // 'parent' map tracks the path for reconstruction.
        std::unordered_map<int, int> parent;
        parent[userId1] = -1; // Mark start node

        while (!q.empty()) {
            int current_user = q.front();
            q.pop();

            if (current_user == userId2) {
                // Path found, now reconstruct it.
                std::string path_str = "";
                int node = userId2;
                while(node != -1) {
                    path_str = std::to_string(node) + (path_str.empty() ? "" : " ") + path_str;
                    node = parent[node];
                }
                return path_str;
            }

            if (connections.count(current_user)) {
                for (int neighbor : connections[current_user]) {
                    if (parent.find(neighbor) == parent.end()) { // If neighbor not visited
                        parent[neighbor] = current_user;
                        q.push(neighbor);
                    }
                }
            }
        }

        return "-"; // No path found
    }
};

/**
 * @brief Processes commands from an input file and writes to an output file.
 * @param system The SocialMediaSystem instance to operate on.
 * @param inputFile The name of the input file.
 * @param outputFile The name of the output file.
 */
void processCommands(SocialMediaSystem& system, const std::string& inputFile, const std::string& outputFile) {
    std::ifstream inFile(inputFile);
    std::ofstream outFile(outputFile);

    if (!inFile.is_open()) {
        std::cerr << "Error: input.txt not found." << std::endl;
        return;
    }

    // This is the dispatch table. It maps command strings to handler functions.
    // It's a much cleaner and more scalable approach than a long if-else-if chain.
    std::unordered_map<std::string, std::function<std::string(std::stringstream&)>> commandHandlers;

    // Handler for "create_user"
    commandHandlers["create_user"] = [&](std::stringstream& ss) -> std::string {
        int userId;
        std::string name, email, isVerifiedStr;
        if (ss >> userId >> name >> email >> isVerifiedStr && (isVerifiedStr == "true" || isVerifiedStr == "false")) {
            std::cout << "  -> Executing 'create_user' with ID: " << userId << ", Name: " << name << std::endl;
            return system.createUser(userId, name, email, isVerifiedStr == "true") ? "true" : "false";
        }
        return "false";
    };

    // Handler for "follow"
    commandHandlers["follow"] = [&](std::stringstream& ss) -> std::string {
        int id1, id2;
        if (ss >> id1 >> id2) {
            std::cout << "  -> Executing 'follow' with User1: " << id1 << ", User2: " << id2 << std::endl;
            return system.follow(id1, id2) ? "true" : "false";
        }
        return "false";
    };

    // Handler for "unfollow"
    commandHandlers["unfollow"] = [&](std::stringstream& ss) -> std::string {
        int id1, id2;
        if (ss >> id1 >> id2) {
            std::cout << "  -> Executing 'unfollow' with User1: " << id1 << ", User2: " << id2 << std::endl;
            return system.unfollow(id1, id2) ? "true" : "false";
        }
        return "false";
    };

    // Handler for "create_post"
    commandHandlers["create_post"] = [&](std::stringstream& ss) -> std::string {
        int postId, userId;
        if (ss >> postId >> userId) {
            std::cout << "  -> Executing 'create_post' with PostID: " << postId << ", UserID: " << userId << std::endl;
            return system.createPost(postId, userId) ? "true" : "false";
        }
        return "false";
    };

    // Handler for "like"
    commandHandlers["like"] = [&](std::stringstream& ss) -> std::string {
        int postId;
        if (ss >> postId) {
            std::cout << "  -> Executing 'like' on PostID: " << postId << std::endl;
            return system.like(postId) ? "true" : "false";
        }
        return "false";
    };

    // Handler for "dislike"
    commandHandlers["dislike"] = [&](std::stringstream& ss) -> std::string {
        int postId;
        if (ss >> postId) {
            std::cout << "  -> Executing 'dislike' on PostID: " << postId << std::endl;
            return system.dislike(postId) ? "true" : "false";
        }
        return "false";
    };
    
    // Handler for "get_user_details"
    commandHandlers["get_user_details"] = [&](std::stringstream& ss) -> std::string {
        int userId;
        if (ss >> userId) {
            std::cout << "  -> Executing 'get_user_details' for UserID: " << userId << std::endl;
            return system.getUserDetails(userId);
        }
        return "false";
    };

    // Handler for "top_posts"
    commandHandlers["top_posts"] = [&](std::stringstream& ss) -> std::string {
        int k;
        if (ss >> k) {
            std::cout << "  -> Executing 'top_posts' for k=" << k << std::endl;
            return system.topPosts(k);
        }
        return "false";
    };

    // Handler for "follow_path"
    commandHandlers["follow_path"] = [&](std::stringstream& ss) -> std::string {
        int id1, id2;
        if (ss >> id1 >> id2) {
            std::cout << "  -> Executing 'follow_path' between User1: " << id1 << ", User2: " << id2 << std::endl;
            return system.followPath(id1, id2);
        }
        return "false";
    };

    std::string line;
    while (std::getline(inFile, line)) {
        std::cout << "DEBUG: Reading line -> " << line << std::endl;
        std::stringstream lineStream(line);
        std::string command;
        lineStream >> command;

        std::string output = "false";
        // Find the command in our map
        if (commandHandlers.count(command)) {
            // If found, execute the corresponding function
            output = commandHandlers[command](lineStream);
        }
        
        outFile << output << std::endl;
    }
    
    std::cout << "Processing complete. Check " << outputFile << " for results." << std::endl;
}

/**
 * @brief Main entry point of the program.
 */
int main() {
    // --- DEBUG: Announce program start ---
    std::cout << "--- Social Media System Initializing ---" << std::endl << std::endl;
    SocialMediaSystem sm_system;
    processCommands(sm_system, "input.txt", "output.txt");
    // --- DEBUG: Announce program end ---
    std::cout << std::endl << "--- Program Terminated ---" << std::endl;
    return 0;
}

