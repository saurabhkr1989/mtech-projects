/*

Assignment 1 : Vigenere Cipher 

Name : Lt Col Dey Sanjeetkumar Narayan 	Entry No: 2025JCS2949
Name : Lt Col Saurabh Kumar Singh 		Entry No: 2025JCS3011

*/



#include <iostream>
#include <fstream>
#include <string>
#include <algorithm>
#include <unordered_map>
#include <vector>
#include <array>
#include <numeric>
#include <cctype>

using namespace std;

string makesafe(const string& s);
string getfile(const string& fname);
string f_cipher_txt_only_char(const string& txt);
int GuessKeyLen(string txt);
void kasiski(const string& text, vector<int>& votes);
double ICfun(string s);
double MIC_fun(const std::string& a, const std::string& b);
int BestShift(const string& s);
string GetKey(const string& txt, int L);
double CheckEng(const std::string& txt);
string decrypt(const string& txt, const string& key);

// English frequency table
extern const std::array<double, 26> freq_English = {0.08167,0.01492,0.02782,0.04253,0.12702,0.02228,0.02015,0.06094,0.06966,0.00153,0.00772,0.04025,0.02406,0.06749,0.07507,0.01929,0.00095,0.05987,0.06327,0.09056,0.02758,0.00978,0.02360,0.00150,0.01974,0.00074};

// read file into a string
string getfile(const string& fname) {
    ifstream file_input_txt(fname);
    if (!file_input_txt) return "Error : Failed to open file. Check availablity of file in the same directory";  // if file can't be opened

    string input_txt((istreambuf_iterator<char>(file_input_txt)), istreambuf_iterator<char>());

    // remove all '\r' characters
    input_txt.erase(remove(input_txt.begin(), input_txt.end(), '\r'), input_txt.end());

    return input_txt;
}

// keep only letters and make them capital
string f_cipher_txt_only_char(const string& txt) {
    string only_char = "";
    for (char c : txt) {
        if (isalpha(c)) {           // check if alphabet
            only_char += toupper(c);      // convert to uppercase
        }
    }
    return only_char;
}
 

// guess key length
int GuessKeyLen(string cipher_txt) {
	
	vector<int> votes(6);
	
	kasiski(cipher_txt, votes);
	
	double ICValue = ICfun(cipher_txt);
    
	int bestL = 1;
    double bestsc = -1e9;
	
    for (int L = 1; L <= 5; L++) {
        // split into groups
        
		vector<string> grp(L);
		
        for (int i = 0; i < cipher_txt.size(); i++) grp[i % L].push_back(cipher_txt[i]);
	
        string key = GetKey(cipher_txt,L);
		
        // mic average
        double MICSum = 0;
        int MIC_Cnt = 0;
        for (int a = 0; a < L; a++) {
            for (int b = a+1; b < L; b++) {
                MICSum += MIC_fun(grp[a], grp[b]);
                MIC_Cnt++;
            }
        }
        double MICAvg = (MIC_Cnt > 0)? MICSum/MIC_Cnt : 0;
		
		// decrypt quickly
        string tmp = "";
        tmp.reserve(cipher_txt.size()); 
        for (int i = 0; i < cipher_txt.size(); i++) {
            int c = cipher_txt[i]-'A';
            int k = key[i%L]-'A';
            int p = (c-k+26)%26;
            tmp.push_back('A' + p);
        }
		
		
        // total score - weights are suggestive in nature and can be modified as per the requirement
        double sc = CheckEng(tmp) + ICValue*100 + votes[L] + MICAvg*100;
		
		//cout<<"IC Values " << ICValue << " and MIC Average " << MICAvg << " \n";

        if (sc > bestsc) {
			cout<<"\033[1;33m Better Key of Length " << L << " with score " << bestsc << " found" << " (IC Value = " << ICValue << " and MIC Average = " << MICAvg << ") \n\n";
	
            bestsc = sc;
            bestL = L;
        }
    }
    return bestL;
}


/*
 Kasiski Examination : Detect repeated substrings in ciphertext (length 3–5).Use their positions to compute "gaps". If a gap is divisible by some candidate key length (2–5), that key length gets a "vote".
*/
void kasiski(const string& text, vector<int>& votes) {
    
	cout << "\033[31m+++++++++++++++++++++++   Implementing Kasiski Method  +++++++++++++++++++++++\n\n";
	
	votes.assign(6, 0);

    int n = text.size();
	
	// Hash map: substring -> list of starting positions
        unordered_map<string, vector<int>> substrPositions;

    for (int subLen = 3; subLen <= 5; subLen++) {

        
        // Extract each substring of length = subLen
        for (int i = 0; i + subLen <= n; i++) {
            string sub = text.substr(i, subLen);

            // If this substring has been seen before
            if (substrPositions.count(sub)) {
                //Compare with all previous positions
                for (int prevIndex : substrPositions[sub]) {
                    int gap = i - prevIndex;  

                    for (int L = 2; L <= 5; L++) {
                        if (gap % L == 0) {
                            votes[L]++;  
                        }
                    }
                }
            }

            // Record substring's position
            substrPositions[sub].push_back(i);
        }
    }
	
	/*
	cout << "Substrings and their positions:\n";
    for (const auto& entry : substrPositions) {
        cout << entry.first << " -> ";
        for (int pos : entry.second) {
            cout << pos << " ";
        }
        cout << endl;
    }
	*/
	
	cout << "+++++++++++++++++++++++   Key length votes after Kasiski Method  +++++++++++++++++++++++\n\n";
	cout <<"Key Length\tVotes\t\n";
	for (int i = 0; i < (int)votes.size(); i++) cout << i << "\t\t" << votes[i] << "\t\n";	cout << endl;
	
	cout << "+++++++++++++++++++++++   Ending Kasiski Method  +++++++++++++++++++++++\n\n";
	
}

// find the key of length L
string GetKey(const string& txt, int L) {
    
	vector<string> groups(L);
    	
	for (int i = 0; i < txt.size(); i++) groups[i % L].push_back(txt[i]);

    string key = "";
    for (int i = 0; i < L; i++) {
        int sh = BestShift(groups[i]);
        key.push_back('A' + sh);   
    }

	//cout << "GetKey Return " << key << "\n" ;
    return key;  
}

// finding best shift (Caesar) for a group
int BestShift(const string& s) {
    
	vector<int> cnt(26, 0);
    for (char c : s) {
        cnt[c - 'A']++;
    }

    int n = s.size();  
    int best = 0;
    double bestscore = -1e9;

    for (int k = 0; k < 26; k++) {
        double score = 0.0;

        // Rotate distribution by k and compare with English freq
        for (int i = 0; i < 26; i++) {
            double fi = static_cast<double>(cnt[(i + k) % 26]) / n;  
            score += fi * freq_English[i];  
        }

        if (score > bestscore) {
            bestscore = score;
            best = k;
        }
    }

	//cout << "BestShift Return " << best << "\n" ;
    
    return best;  
}


// Index of Coincidence for one string
double ICfun(string s) {
    int cnt[26];
    for (int i = 0; i < 26; i++) cnt[i] = 0;
    for (int i = 0; i < s.size(); i++) {
        cnt[s[i]-'A']++;
    }
    double top = 0;
    for (int i = 0; i < 26; i++) {
        top = top + cnt[i]*(cnt[i]-1);
    }
    double n = s.size();
    if (n < 2) return 0;
	
	//cout << "IC Function Return " << (top / (n*(n-1)) << "\n" ;
    
    return top / (n*(n-1));
}

// MIC between two strings
double MIC_fun(const std::string& a, const std::string& b) {
	
    if (a.empty() || b.empty()) return 0.0;

    std::array<int, 26> ca{}, cb{}; // zero-initialized

    for (char c : a) ca[c - 'A']++;
    for (char c : b) cb[c - 'A']++;

    double n1 = static_cast<double>(a.size());
    double n2 = static_cast<double>(b.size());

    double sum = std::inner_product(ca.begin(), ca.end(), cb.begin(), 0.0);

	//cout << "MIC Function Return " << (sum / (n1 * n2)) << "\n" ;

    return sum / (n1 * n2);
}




// score english-likeness
double CheckEng(const std::string& txt) {
    std::array<int, 26> cnt{}; 
    int n = 0;

    // Count letters
    for (char c : txt) {
        if (std::isalpha(static_cast<unsigned char>(c))) {
            char upper = std::toupper(static_cast<unsigned char>(c));
            cnt[upper - 'A']++;
            n++;
        }
    }

    if (n == 0) return -99999.0; 

    double sc = 0.0;
    for (int i = 0; i < 26; i++) {
        double expected = freq_English[i] * n;
        double diff = cnt[i] - expected;
        sc -= (diff * diff) / (expected + 1e-4); 
    }

	//cout << "CheckEng Function Return " << sc << "\n" ;

    return sc;
}


// decrypt full text with key
string decrypt(const string& txt, const string& key) {
    string out;
    out.reserve(txt.size());

    size_t j = 0; 

    auto decrypt_char = [&](char c, int shift) -> char {
        if (isupper(static_cast<unsigned char>(c))) {
            return 'A' + (c - 'A' - shift + 26) % 26;
        }
        if (islower(static_cast<unsigned char>(c))) {
            return 'a' + (c - 'a' - shift + 26) % 26;
        }
        return c; 
    };

    for (char c : txt) {
        if (isalpha(static_cast<unsigned char>(c))) {
            int shift = key[j % key.size()] - 'A'; 
            out.push_back(decrypt_char(c, shift));
            ++j;
        } else {
            out.push_back(c);
        }
    }
	
	//cout << "decrypt Function Return " << out << "\n" ;
	
    return out;
}

// escape special for JSON
string makesafe(const string& s) {
    string out;
    out.reserve(s.size() * 2); // worst case: every char needs escaping

    for (char c : s) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '\"': out += "\\\""; break;
            default:   out += c;      break;
        }
    }
	
		//cout << "Makesafe Function Return " << out << "\n" ;

    return out;
}

int main() {
	
    string cipher_txt = getfile("input.txt");			//input file
	
	// cout<<"\033[1;32m************************************************ Entered Cipher Text ***************************************************\n\n";
	// cout<<cipher_txt<<"\n\n";
	
    string cipher_txt_only_char = f_cipher_txt_only_char(cipher_txt);		//remove special characters
    
	cout<<"\033[1;32m********************************************* Entered Cipher Text : After Removing Special Characters *************************************************\n\n";
	cout<<cipher_txt_only_char<<"\n\n";
	
	cout<<"\033[1;33m##############################    Guessing Key   ##################################\n\n";
	//cout<<cipher_txt_only_char<<"\n\n";
	
	int Key_Length = GuessKeyLen(cipher_txt_only_char);
	
	string probable_key = GetKey(cipher_txt_only_char,Key_Length);
	
	cout<<" Most Suitable Key : " << probable_key <<   "\n\n";
	
    string plain_txt = decrypt(cipher_txt,probable_key);

	cout<<"\033[1;32m********************************************* Likely Plain Text  *************************************************\n\n";
	cout<<plain_txt<<"\n\n";
	
    ofstream file_output("output.json");
    file_output << "{\n";
    file_output << "  \"key\": \"" << probable_key << "\",\n";
    file_output << "  \"plaintext\": \"" << makesafe(plain_txt) << "\"\n";
    file_output << "}";
    file_output.close();

    cout<<"\033[0m##############################    Data Written in JSON File. Please Check \"output.json\"   ##################################\n\n";
	
	return 0;
}
