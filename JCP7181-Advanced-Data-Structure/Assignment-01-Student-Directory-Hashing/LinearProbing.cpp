#include "HashDefs.h"
#include <iostream>
using namespace std ;        

// Implements a Linear Probing hash table with detailed batch insert statistics.                      
class LinearProbingHashTable {              

    StudentRecord table[HASH_TABLE_CAPACITY] ;  // Fixed size array to hold records             

    // Hash function: sums ASCII values of email characters to generate initial index.             
    int converter(const string& studentEmail) {


        int totalAscii = 0 ;             
        for (char c : studentEmail) totalAscii += static_cast<int>(c) ;

        return totalAscii ;                
    }
             
public:
    // Constructor initializes the entire table to empty (non-deleted) slots.
    LinearProbingHashTable() 
	{

        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) table[i] = StudentRecord() ;
    }
           
    /*           
      Single record insertion or update: linear probing on collision.
      Returns number of collision probes or -1 if insertion fails due to full table.          
    */
    int add(const string& studentEmail, const string& studentName) {
        int startIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;         
		
        int idx = startIndex ;
		
		
        int collisions = 0 ;             
		
               
        do {
            if (table[idx].studentEmail.empty() || table[idx].isDeleted || table[idx].studentEmail == studentEmail) 
			{     


                table[idx] = StudentRecord(studentEmail, studentName, false) ;           
				
                return collisions ;                     
            }
            
            idx = (idx + 1) % HASH_TABLE_CAPACITY ;               
			
			
            ++collisions ;

        } while (idx != startIndex) ;            

        // Table is full ; no free slot was found.             
        return -1 ;             
    }

    // Struct to encapsulate batch insertion results including successes, failures, and total collisions.                               
    struct BatchInsertResult 
	{              
        int insertedCount = 0 ;    // Number of successfully inserted or updated records         
		
        int failedCount   = 0 ;    // Number of records failed to insert (table full)            
		
        int totalCollisions = 0 ;  // Sum of collisions encountered during successful insertions        
		
    } ;

    /*             
      Batch insertion of multiple records.            
      Returns detailed batch insertion results.
    */            
    BatchInsertResult addBatch(const vector<pair<string, string>>& records) 
	{       

	
        BatchInsertResult result ;             

        for (const auto& rec : records) {               
		
            int collisionCount = this->add(rec.first, rec.second) ;               
			
			
            if (collisionCount == -1) {              
			
                result.failedCount++ ;             
				
            } else 
			{
                result.insertedCount++ ;               
				
				
                result.totalCollisions += collisionCount ;
            }
        }
        return result ;                               
    }
             
    // Search for a matching active record by studentEmail ; return pointer or nullptr if absent.                      
    StudentRecord* find(const string& studentEmail) {               
	
        int startIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;
		
        int idx = startIndex ;               
		
        int checkedSlots = 0 ;
             
        while (!table[idx].studentEmail.empty() && checkedSlots < HASH_TABLE_CAPACITY) 
		{
			
			
            if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) return &table[idx] ;              

            idx = (idx + 1) % HASH_TABLE_CAPACITY ;        
			
            ++checkedSlots ;
        }              
        return nullptr ;
    }

    // Returns index of record if found and active, else -1.
    int find_index(const string& studentEmail) {
		
        int startIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;     
		
        int idx = startIndex ;
		
        int checkedSlots = 0 ;               
                
        while (!table[idx].studentEmail.empty() && checkedSlots < HASH_TABLE_CAPACITY) 
		{      

		
            if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) return idx ;              

            idx = (idx + 1) % HASH_TABLE_CAPACITY ;
			
            ++checkedSlots ;
        }                         
        return -1 ;                    
    }               

    // Logical deletion: marks the matching record as deleted.                           
    bool delete_record(const string& studentEmail) {          
	
        int startIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;   
		
        int idx = startIndex ;
		
        int checkedSlots = 0 ;                         

        while (!table[idx].studentEmail.empty() && checkedSlots < HASH_TABLE_CAPACITY) 
		{     
		
            if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) {                  

			
                table[idx].isDeleted = true ;
                return true ;       
            }
            idx = (idx + 1) % HASH_TABLE_CAPACITY ;
			
            ++checkedSlots ;
        }
        return false ;
    }

    // Prints content of the entire hash table displaying empty, deleted or active records.               
    void view_table() {                           
        cout << "\n---- Linear Probing Hash Table ----\n" ;                   
        for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i)
			{             
		
            cout << "Index " << i << ": " ;            
			
            if (table[i].studentEmail.empty())               
				
                cout << "[Empty]" ;              
            else if (table[i].isDeleted)
				
                cout << "[Deleted]" ;                 
            else
				
                cout << table[i].studentEmail << " | " << table[i].studentName ;
				
            cout << "\n" ;                      
        }                              
    }             
                     
    // Counts currently active student records (non-empty and not logically deleted).
    int occupancy() 
	
	{              
	
        int count = 0 ;
		
        for (const auto& rec : table)             
			
            if (!rec.studentEmail.empty() && !rec.isDeleted)       
				
                ++count ;               
				
        return count ;                 
		
    }
} ;            


