#include "HashDefs.h"
#include <iostream>
using namespace std ;
          
/* Quadratic Probing Hash Table implementing insertion with quadratic probing to reduce clustering.
*/
                
class QuadraticProbingHashTable {
                                 
  StudentRecord table[HASH_TABLE_CAPACITY] ;
                       
    // Hash function computing sum of ASCII character codes in the student email.
        int converter(const string& studentEmail) {
        long long h = 0;
        const long long MOD = 1000000007LL;
        for (unsigned char c : studentEmail) h = (h * 131 + c) % MOD;
        return static_cast<int>(h);
    }

    /*
      Alternating-sign quadratic probing: step 0 -> base, step 1 -> base+1^2,
      step 2 -> base-1^2, step 3 -> base+2^2, step 4 -> base-2^2, ...
      For a prime table size p with p % 4 == 3 (199 % 4 == 3 here), this
      sequence is known to visit every one of the p slots exactly once as
      step ranges 0..p-1, unlike plain "+i*i" quadratic probing which only
      reaches about half the table.
    */
    int probeIndex(int base, int step) {
        int k = (step + 1) / 2;
        int sign = (step % 2 == 1) ? 1 : -1;
        long long off = (long long)k * k * sign;
        long long idx = ((long long)base + off) % HASH_TABLE_CAPACITY;
        if (idx < 0) idx += HASH_TABLE_CAPACITY;
        return static_cast<int>(idx);
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
			               
            int idx = probeIndex(baseIndex, i) ;                                          
 
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
            int idx = probeIndex(baseIndex, i) ;   
			
            if (table[idx].studentEmail.empty()) break ;  
            
			if (!table[idx].isDeleted && table[idx].studentEmail == studentEmail) return &table[idx] ;
			
        }
        return nullptr ;
    }

    // Returns index of an active record or -1 if the same was not found .
    int find_index(const string& studentEmail) {  
          
		int baseIndex = converter(studentEmail) % HASH_TABLE_CAPACITY ;   
          
		for (int i = 0 ; i < HASH_TABLE_CAPACITY ; ++i) {  
          
			int idx = probeIndex(baseIndex, i) ;
            
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
            int idx = probeIndex(baseIndex, i) ;
			  
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
