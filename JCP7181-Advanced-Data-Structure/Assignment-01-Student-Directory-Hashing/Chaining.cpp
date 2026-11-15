#include "HashDefs.h"
#include <list>
#include <iostream>
using namespace std ;

/*
Implements Separate Chaining hash table. Each bucket is a linked list storing colliding entries.
*/ 

class SeparateChainingHashTable { 
    
	list<StudentRecord> buckets[HASH_TABLE_CAPACITY] ; 
 
        int converter(const string& studentEmail) {
        long long h = 0;
        const long long MOD = 1000000007LL;
        for (unsigned char c : studentEmail) h = (h * 131 + c) % MOD;
        return static_cast<int>(h);
    }

public: 
    SeparateChainingHashTable() {}    

    // Insert a single record into bucket chain only if duplicate is not found in the existing record and thereafter returns updated chain length, or existing length if duplicate entry is found.     
    int add(const string& studentEmail, const string& studentName) {                                                
        
		int idx = converter(studentEmail) % HASH_TABLE_CAPACITY ;      
 
        for (const auto& rec : buckets[idx]) {     
		
            if (rec.studentEmail == studentEmail)  
			{
				return buckets[idx].size() ; // No insertion for duplicates.
			}
        }     

        buckets[idx].emplace_back(studentEmail, studentName) ;
        
		
		
		return buckets[idx].size() ;
    }

		struct BatchInsertResult {   
        
		int insertedCount = 0 ;
        
		int failedCount = 0; // Will remain zero for chaining since it grows dynamically.
        
		int totalCollisions = 0; // Total sum of increments in chain lengths due to insertions.     
    } ;

    BatchInsertResult addBatch(const vector<pair<string, string>>& records) {   
        
		BatchInsertResult result ;
                               
        for (const auto& rec : records) {
            
			int idx = converter(rec.first) % HASH_TABLE_CAPACITY ;
            
			int beforeLen = buckets[idx].size() ;
            
			int res = add(rec.first, rec.second) ;      
            
			if (res == beforeLen) {
                // Duplicate: no insertion.
            
				continue ;
            } else if (res > beforeLen) 
			
			{      
                result.insertedCount++ ;
                result.totalCollisions += (res - beforeLen) ;
            } 
			else 
			{
                // Ideally this should not occur and keeps track of any unexpected failures.
            
			result.failedCount++ ;
            }      
        }       
        
        return result ;
    }

    // Find record by email ID and return the pointer or return nullptr if the entry is not found.
    StudentRecord* find(const string& studentEmail) {
        
		int idx = converter(studentEmail) % HASH_TABLE_CAPACITY ;      
        
		for (auto& rec : buckets[idx]) {
        
		if (rec.studentEmail == studentEmail) return &rec ;     

        }
		
        return nullptr ;
    }

    // Find bucket index containing the email otherwise return -1.
    int find_index(const string& studentEmail) {
        
		int idx = converter(studentEmail) % HASH_TABLE_CAPACITY ;
        
		for (auto& rec : buckets[idx]) {        
        
		if (rec.studentEmail == studentEmail) return idx ;         
        }
        return -1 ;
    }

    // Delete record matching email and returns true if successful.
    bool delete_record(const string& studentEmail) {       

        int idx = converter(studentEmail) % HASH_TABLE_CAPACITY ;

        for (auto it = buckets[idx].begin() ; it != buckets[idx].end() ; ++it) {

            if (it->studentEmail == studentEmail) {       

                buckets[idx].erase(it) ;      

                return true ;
            }
        }

        return false ;       
    }

    // Display complete table with bucket contents.
void view_table() {

    cout << "\n---- Separate Chaining Hash Table Contents ----\n" ;        
    
    int emptyBuckets = 0 ;       // Counter for buckets with zero entries

    int totalChainLength = 0 ;   // Sum of all chain lengths (number of entries across buckets)        
    
    // Iterate through each bucket to display content and accumulate data to be displayed as summary at the end          
    for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {

        cout << "Bucket " << i << ": " ;
        
        if (buckets[i].empty()) {

            cout << "[Empty]" ;

            ++emptyBuckets ;  // Increment count for unused bucket       
        } 
		else 
		{
            // Display all records in chain
            for (const auto& rec : buckets[i]) {
        
				cout << "[" << rec.studentEmail << " | " << rec.studentName << "] " ;     
            }
            
			totalChainLength += (int)buckets[i].size() ;     
        }
        
		cout << '\n' ;
    }

    // Calculate number of non-empty buckets to avoid division by zero     
    int usedBuckets = HASH_TABLE_CAPACITY - emptyBuckets ;     
    
	double averageChainLength = (usedBuckets > 0) ? static_cast<double>(totalChainLength) / usedBuckets : 0.0 ;       

    // Display summary after table view
    cout << "\nSummary:\n" ;
    cout << "Total Buckets         : " << HASH_TABLE_CAPACITY << '\n' ;
    
	cout << "Unused (Empty) Buckets: " << emptyBuckets << '\n' ;
    cout << "Used Buckets          : " << usedBuckets << '\n' ;
    
	cout << "Total Entries         : " << totalChainLength << '\n' ;        
    cout << "Average Chain Length  : " << averageChainLength << '\n' ;     
}

    // Returns total number of stored records.
    int occupancy() {      
    
		int count = 0 ;
        for (auto& chain : buckets) count += (int)chain.size() ;       
        
		return count ;      
    }

    // Returns total collisions (entries beyond first per bucket) and average chain length.
    pair<int, double> chaining_collision_stats() {
        
		int totalCollisions = 0 ;      
        
		int nonEmptyBuckets = 0 ;      
        
		int totalEntries = 0 ;    

        for (auto& chain : buckets) {
        
			int len = (int)chain.size() ;
            if (len > 0) 
			{     
            
				nonEmptyBuckets++ ;       
                
				totalEntries += len ;     
                
				if (len > 1) totalCollisions += (len - 1) ;       
            }
        }

        double avgLength = nonEmptyBuckets ? (double)totalEntries / nonEmptyBuckets : 0.0 ;      
        
		return {totalCollisions, avgLength} ;     
    }  

	
} ;
