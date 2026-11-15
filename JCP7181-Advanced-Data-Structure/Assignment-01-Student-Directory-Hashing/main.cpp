
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>

#include "HashDefs.h"
#include "LinearProbing.cpp"
#include "QuadraticProbing.cpp"
#include "Chaining.cpp" 

using namespace std ;
   
void displayWelcomeScreen()  
{  
    cout << "\n********************************* IIT Delhi Student Directory ***************************************\n";
    cout << "Hashing Algorithms Available:\n" ;
    cout << "1. Linear Probing\n2. Quadratic Probing\n3. Separate Chaining\n\n" ;
    cout << "Operations Supported: Insert, Search, Delete, View, Benchmark or Performance Comparison.\n";
    cout << "  ********************************************************************************************************\n" ;
}

// Structure for user input of student data
struct InputRecord { 
    
	string email;    
    string name; 
} ;
  
// Reading student records from a file
vector<InputRecord> loadFromFile(const string& filename) 
{
     
	vector<InputRecord> records;
    ifstream file_input(filename);  
    if (!file_input.is_open())  
	{   
        cerr << "Unable to open file: " << filename << "\n Kindly check the filename or file permissions" ;		//display error if unable to open the file
        return records ;    
    }
    string line ;		//assuming that every line contains a student record
    int lineNum = 0 ;   
    while (getline(file_input, line)) {	//continue till the time input is being received. 
		
        if (line.empty()) continue;		//	End moment and empty line is encountered
        lineNum++ ;   
        istringstream temp_student(line);     
        InputRecord rec ; 
        temp_student >> rec.email ;	 
        getline(temp_student, rec.name);   
          
		//removing the leading spaces
		if (!rec.name.empty() && rec.name[0] == ' ') rec.name.erase(0,1);
        
		//checking blank entries  
		if (rec.email.empty() || rec.name.empty()) {
            cerr << "Invalid format encountered in file at line " << lineNum << ": " << line << "\n";
            continue ;
        }
		
        records.push_back(rec);
    } 
	
    file_input.close() ;  
    
	cout << "Processed " << records.size() << " records from '" << filename << "'\n";
    
	return records ; 
} 
 
// Collecting student records manually.
vector<InputRecord> manual_Input() 
{  
    vector<InputRecord> records ;
    cout << "Enter students (enter empty email to stop):\n" ;
     
	while (true)   
	{
        cout << "Email ID : " ;   
         
		string email ;  
		 
		getline(cin,email) ; 
        
		if (email.empty()) break;    
        
		cout << "Name : ";         
        
		string name ; getline(cin,name);      
        
		if (name.empty()) break ;	   	
        
		records.push_back({email,name});  
    }
    return records ;   
}

// Returns algorithm name.
string getAlgorithmName(int choice) {   
    switch(choice) { 
        case 1: return "Linear Probing"; 
        case 2: return "Quadratic Probing";      
        case 3: return "Separate Chaining" ;      
        default: return "None" ;            
    }      
} 

// Converts a vector of InputRecord structs to a vector of (email, name) pairs. This is necessary for passing batch insertion data to hashing classes which accept pairs.
vector< pair< string,  string>> convertToPairs(const  vector<InputRecord>& records)  
{       
     vector< pair< string,  string>> pairs; 
    for (const auto& rec : records) { 
        pairs.emplace_back(rec.email, rec.name); 
    }     
    return pairs ;     
}
    
int main() {
    
	displayWelcomeScreen() ;
        
    LinearProbingHashTable linearTable ;
    QuadraticProbingHashTable quadraticTable;
    SeparateChainingHashTable chainingTable;
      
    int selectedAlgorithm = 0 ;
    vector<InputRecord> linearData, quadraticData, chainingData;
     
    string input ;      
    while (true) {    
        cout << "\nSelected Algorithm: " << getAlgorithmName(selectedAlgorithm) << "\n";
        cout << "Menu:\n0) Exit\n1) Select Algorithm\n2) Add Records\n3) Search\n4) Delete\n5) View Table\n6) Benchmark or Comaprative Analysis\nChoice: " ;
        getline(cin, input) ;      

        if (input == "0")    
		{   
                     
			cout << "Exiting!!! Thanks!\n";
            break ;
			       
        } else if (input == "1") {
            
			cout << "Select Algorithm (Input 1 for Linear, 2 for Quadratic or 3 for Separate Chaining): "  ;  
            getline(cin, input) ;       
            
			try {    
                int choice = stoi(input) ;    
                
				if (choice<1 || choice>3) throw invalid_argument("Invalid"); 
                
				selectedAlgorithm = choice ;    
                
				cout << "Algorithm set to " << getAlgorithmName(choice) << ". Clearing previous data.\n";     
                
				if (choice==1) 
				{         
					linearTable=LinearProbingHashTable() ;        
					linearData.clear() ;  
					}  
                          
				else if (choice==2)    
				{
					quadraticTable=QuadraticProbingHashTable() ;    
					quadraticData.clear();  
					}  
                
				else {       
					chainingTable=SeparateChainingHashTable();       
					chainingData.clear() ; 
					}      
                   
			} catch (...) {       
                cout << "Invalid Choice. Input Again\n" ;    
            }     
        }      
		else if (input == "2") {
			
            if (selectedAlgorithm==0) 
			{            
				cout<<"Please select an algorithm before entering the data.\n";             
				continue ;
				}              
            cout << "Add records: For Bulk Entry through file enter 1 and for Manual Entry enter 2: " ;
            getline(cin, input) ;
                      
			vector<InputRecord> newRecords ;
                     
			if (input=="1") {         
                cout << "Enter the name of the file (Ensure the file is present and accessible in the same directory): ";
                string fname ; 
				getline(cin,fname) ;       
                newRecords = loadFromFile(fname);
            }            
			else if (input=="2") 
			{
                           
				newRecords = manual_Input();
            }        
			else {
                
				cout << "Invalid input.\n" ;           
                continue ;
            }

            if (selectedAlgorithm==1) {         
                
				auto res = linearTable.addBatch(convertToPairs(newRecords)) ;
                cout << res.insertedCount << " records inserted successfully. \n";
               
			   cout << res.failedCount << " records failed to insert [Hash Table may be full or cyclic collision has been encountered]. \n";

                cout << "Total collisions encountered: " << res.totalCollisions << ".\n" ;
          
                cout << "Current occupancy: " << linearTable.occupancy() << "/" << HASH_TABLE_CAPACITY << "\n" ;
           
                linearData.insert(linearData.end(), newRecords.begin(), newRecords.end());        
 
           } 
		   else if (selectedAlgorithm==2)         
			   {
                auto res = quadraticTable.addBatch(convertToPairs(newRecords)) ;
                
				cout << res.insertedCount << " records inserted successfully.\n";
                
				cout << res.failedCount << " records failed to insert [Hash Table may be full or cyclic collision has been encountered].\n";       
                              
				cout << "Total collisions encountered: " << res.totalCollisions << ".\n";
                
				cout << "Current occupancy: " << quadraticTable.occupancy() << "/" << HASH_TABLE_CAPACITY << "\n" ;         
                
				quadraticData.insert(quadraticData.end(), newRecords.begin(), newRecords.end()) ;         
            } else { 
                auto res = chainingTable.addBatch(convertToPairs(newRecords)) ;  
                
				cout << res.insertedCount << " records inserted successfully.\n";  
                
				cout << res.failedCount << " records failed to insert.\n";  
                
				cout << "Total collisions encountered: " << res.totalCollisions << ".\n" ;   
                
				cout << "Current occupancy: " << chainingTable.occupancy() << " entries\n";   
                
				chainingData.insert(chainingData.end(), newRecords.begin(), newRecords.end()) ;  
            }
        } 
		else if (input == "3")   
		{
			
            if (selectedAlgorithm==0) {cout << "Please select an algorithm before searching the data.\n" ;    continue; }  
            
			cout << "Enter the Email ID to search: ";  
            string email ; getline(cin,email) ;  
            
			StudentRecord* found = nullptr;  
            int index = -1 ;
            
			if (selectedAlgorithm==1)   
			{
			
				found=linearTable.find(email) ;   
				if (found) {
					
					index = linearTable.find_index(email) ;  
					cout<< "Found Email : " << found->studentEmail << ", Name : " << found->studentName << " at Index : " << index;   
				
				}  
			}  
            
			else if (selectedAlgorithm==2) {  
				
				found=quadraticTable.find(email) ;  
				if (found){
					index = quadraticTable.find_index(email) ;  
										cout<< "Found Email : " << found->studentEmail << ", Name : " << found->studentName << " at Index : " << index ;   
				}   
			}  
				
            else {   
				found=chainingTable.find(email);   
				if (found) {
					index = chainingTable.find_index(email) ;
										cout<< "Found Email : " << found->studentEmail << ", Name : " << found->studentName << " at Index (Bucket) : " << index  ;
				}
			}
			// if (found) cout << "Found: " << found->studentEmail << ", " << found->studentEmail << " at bucket " << index << "\n" ;
            if (!found) cout << "No record has been found with given Email ID. Pease check again\n" ;
        } 
		else if (input == "4")     
		{
            
			if (selectedAlgorithm==0) {cout << "Please select an algorithm before deleting the data.\n"; continue; }
            
			cout << "Enter email to delete: ";
            
			string email ; getline(cin,email) ;   
            
			bool deleted = false ;
            
			if (selectedAlgorithm==1) deleted=linearTable.delete_record(email);
            
			else if (selectedAlgorithm==2) deleted=quadraticTable.delete_record(email); 
            
			else deleted=chainingTable.delete_record(email) ;
            
			if (deleted) cout << "Deleted Successfully.\n" ;
            
			else cout << "No record has been found with given Email ID. \n";
            
			int occ = selectedAlgorithm==1 ? linearTable.occupancy() : selectedAlgorithm==2 ? quadraticTable.occupancy() : chainingTable.occupancy() ;
            
			cout << "Current occupancy: " << occ << (selectedAlgorithm==3 ? " entries" : "/" + to_string(HASH_TABLE_CAPACITY)) << "\n" ;
        } 
		
		else if (input == "5")
		{
            if (selectedAlgorithm==0) {cout << "Please select an algorithm before viewing the table.\n" ; continue ;}
            cout << "Displaying current table:\n" ;
            
			if (selectedAlgorithm==1) linearTable.view_table() ;
            
			else if (selectedAlgorithm==2) quadraticTable.view_table();
            
			else chainingTable.view_table(); 
        } 
		
		else if (input == "6") {
            cout << "Benchmarking selected.\nInput data for comparative analysis: Enter 1 for entering data from File and 2 for Manual entries: " ;
            string inp; 
			
			getline(cin,inp) ;
            vector<InputRecord> benchData ;
            
			if (inp=="1") 
			{
                cout << "Filename: " ;
                string f ; 
				getline(cin,f) ;
                benchData = loadFromFile(f);
            } 
			else if (inp=="2") 
			{
            
			benchData = manual_Input() ;
            } 
			
			else {
                cout << "Invalid input.\n" ;
                continue ;
            }

            LinearProbingHashTable benchLP ;
            QuadraticProbingHashTable benchQP ;
            SeparateChainingHashTable benchSC ;
            int lpColl=0, qpColl=0 ;

            for (auto& r : benchData) 
			{
                
				int c=benchLP.add(r.email,r.name) ;
                
				if(c>0) lpColl+=c ;
                
				c=benchQP.add(r.email,r.name) ;
                
				if(c>0) qpColl+=c ;
                benchSC.add(r.email,r.name) ;
            }
            auto [scColl, avgLen] = benchSC.chaining_collision_stats();

            cout << "\nBenchmark or Performance Comparision Results:\n"
                << "Algorithm         | Collisions / Avg Chain Length\n"
                << "*******************************************************\n"
                << "Linear Probing    | " << lpColl << "\n"
                << "Quadratic Probing | " << qpColl << "\n"
                << fixed << setprecision(2)
                << "Separate Chaining | " << scColl << " / " << avgLen << "\n\n" ;
        } 
		else {
            cout << "Invalid Choice.\n" ;
        }
		
    }
    return 0 ;
}

