#ifndef HASH_DEFS_H
#define HASH_DEFS_H
               
#include <string>               

/* Shared global constant defining the size of the hash tables used by all algorithms. Ensures consistency and simplifies benchmarking across different implementations.                               
*/
const int HASH_TABLE_CAPACITY = 199 ;
           
/* StudentRecord represents the data structure stored in the hash table indexes. Each record comprises a unique student email key, the student's full name, and a deletion flag used in open addressing methods to mark logical deletions.
*/

struct StudentRecord {                  
    
	std::string studentEmail ;   // Unique email ID, used as the key for hashing and lookups.
    
	std::string studentName ;    // Full name of the student.                     
    
	bool isDeleted ;             // Flag indicating logical deletion (used in probing methods).

    // Default constructor initializes an empty, active (not deleted) record.                     
    StudentRecord() : studentEmail(""), studentName(""), isDeleted(false) {}
              
    // Construct a record with given email, name, and optional deletion flag.
    StudentRecord(const std::string& email, const std::string& name, bool deleted = false) : studentEmail(email), studentName(name), isDeleted(deleted) {}
	
} ;

#endif
