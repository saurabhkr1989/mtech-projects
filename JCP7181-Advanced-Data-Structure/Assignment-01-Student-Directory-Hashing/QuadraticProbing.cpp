#include "HashDefs.h"
#include <iostream>
using namespace std ;
          
/* Quadratic Probing Hash Table implementing insertion with quadratic probing to reduce clustering.
*/
                
class QuadraticProbingHashTable {
                                 
  StudentRecord table[HASH_TABLE_CAPACITY] ;
                       
    // Hash function computing sum of ASCII character codes in the student email.
    int converter(const string& studentEmail) {                        
                    
        int total = 0 ;
                    
        for (char c : studentEmail)                 
		{    
			total += static_cast<int>(c) ;               
		}     
                            
        return total ;                 
    }
        
public:                  
    QuadraticProbingHashTable() {                         
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i)    

			
            table[i] = StudentRecord() ;   
    }                         
                     
    /*                     
      Inserts or updates a single record. Returns the number of collision probes encountered, or -1 if  the table is full.
    */                          
    int add(const string& studentEmail, const string& studentName) {                              
        int baseIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;                                             
        int collisions = 0 ;        
                                     
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {
			               
            int idx = (baseIndex + i * i) % HASH_TABLE_CAPACITY ;                                          
 
            if (table[idx].studentEmail.empty() || table[idx].isDeleted)                
			{   
                table[idx] = StudentRecord(studentEmail, studentName, false) ;                     
				
				                 
                return collisions ;                       
            }  
               
            if (table[idx].studentEmail == studentEmail) {  
			            
			              
                // Update the existing record.
                table[idx].studentName = studentName ;                   
                         
				return collisions ;                 
            }
			                
            ++collisions ;
        }
                                        
		
		                //either the table is full or no slot was found even after wrap around 
		return -1 ;
    }

    // Struct to aggregate batch insert operation statistics.
    struct BatchInsertResult {
		
        int insertedCount = 0 ;    // Number of successful insertions or updates                                    
        
		int failedCount = 0 ;      // Number of failures due to full table
                              
		int totalCollisions = 0 ;  // Total collision probes summed across all insertions
    } ;                 
	
	
	

    /*                         
      Batch insertion of multiple student records. It will also returns a summary of the insertions including counts and collisions.
    */
    BatchInsertResult addBatch(const vector<pair<string, string>>& records) {
        
		
		BatchInsertResult result ;                 

        for (const auto& rec : records) {       
        
			int collisionCount = add(rec.first, rec.second) ;       
            
			if (collisionCount == -1) 
			{
                ++result.failedCount ;          
            }    
			else 
			{
                ++result.insertedCount ;
            

				result.totalCollisions += collisionCount ;        
            }
        }
        return result ;
		
    }

    // Searches for an active student record by email and returns the pointer or nullptr if the record is not found.
    StudentRecord* find(const string& studentEmail) {
        int baseIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {  
            int idx = (baseIndex + i * i) % HASH_TABLE_CAPACITY ;   
			
            if (table[idx].studentEmail.empty()) break ;  
            
			if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) return &table[idx] ;
			
        }
        return nullptr ;
    }

    // Returns index of an active record or -1 if the same was not found .
    int find_index(const string& studentEmail) {  
          
		int baseIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;   
          
		for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {  
          
			int idx = (baseIndex + i * i) % HASH_TABLE_CAPACITY ;
            
			if (table[idx].studentEmail.empty()) break ;  
               
			if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) return idx ;   
        }
		   
		
        return -1 ;
      
	   
	}

    /* Marks the record logically deleted to ensure that the entire hash table is not disrupted.  
*/	
    bool delete_record(const string& studentEmail) {  
		
        int baseIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;  
		
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {  
            int idx = (baseIndex + i * i) % HASH_TABLE_CAPACITY ;
			  
            if (table[idx].studentEmail.empty()) break ;
			
            if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) {   
                table[idx].isDeleted = true ;   
				  
                return true ;  
            }
			
        }
        return false ;
		
    }

    // Prints comprehensive state of the hash table.
    void view_table() {
		
		
        cout << "\n---- Quadratic Probing Hash Table ----\n" ;
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {   
			   
			
            cout << "Index " << i << ": " ;       
            if (table[i].studentEmail.empty()) cout << "[Empty]" ;   
			
            else if (table[i].isDeleted) cout << "[Deleted]" ;     
			
            else cout << table[i].studentEmail << " | " << table[i].studentName ;     
			
            cout << "\n" ;  
        } 
    }

    // Returns count of active (non-deleted) records in the table.           
    int occupancy() {      
		
		
        int count = 0 ;   
        for (const auto& rec : table)   
			
            if (!rec.studentEmail.empty() && !rec.isDeleted) ++count ;    
        return count ;
		
		
    }
} ;


/*
#ifndef HASH_DEFS_H
#define HASH_DEFS_H

#include <string>

// Shared global constant defining the size of the hash tables used by all algorithms.
// Ensures consistency and simplifies benchmarking across different implementations.
const int HASH_TABLE_CAPACITY = 200 ;

// StudentRecord represents the data structure stored in the hash table indexes.
// Each record comprises a unique student email key, the student's full name,
// and a deletion flag used in open addressing methods to mark logical deletions.
struct StudentRecord {
    std::string studentEmail ;   // Unique email ID, used as the key for hashing and lookups.
    std::string studentName ;    // Full name of the student.
    bool isDeleted ;             // Flag indicating logical deletion (used in probing methods).

    // Default constructor initializes an empty, active (not deleted) record.
    StudentRecord() : studentEmail(""), studentName(""), isDeleted(false) {}

    // Construct a record with given email, name, and optional deletion flag.
    StudentRecord(const std::string& email, const std::string& name, bool deleted = false)
        : studentEmail(email), studentName(name), isDeleted(deleted) {}
} ;

#endif
*/