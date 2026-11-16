"""
N-Gram Statistical Data
Source : http://practicalcryptography.com/
Values are log10 probabilities based on raw frequency counts of above source.
"""

import math

# MONOGRAMS 
ENGLISH_MONOGRAMS = {
    'E': -0.91, 'T': -1.04, 'A': -1.06, 'O': -1.12, 'I': -1.13, 'N': -1.14,
    'S': -1.17, 'R': -1.19, 'H': -1.30, 'L': -1.37, 'D': -1.41, 'C': -1.49,
    'U': -1.57, 'M': -1.59, 'F': -1.66, 'G': -1.68, 'P': -1.68, 'W': -1.73,
    'Y': -1.76, 'B': -1.79, 'V': -1.97, 'K': -2.09, 'J': -2.65, 'X': -2.71,
    'Z': -2.94, 'Q': -2.98
}

# BIGRAMS (Top 100)
ENGLISH_BIGRAMS = {
    'TH': -1.52, 'HE': -1.59, 'IN': -1.65, 'ER': -1.70, 'AN': -1.72, 'RE': -1.78,
    'ON': -1.80, 'AT': -1.82, 'EN': -1.83, 'ND': -1.85, 'TI': -1.88, 'ES': -1.88,
    'OR': -1.89, 'TE': -1.90, 'OF': -1.91, 'ED': -1.92, 'IS': -1.93, 'IT': -1.93,
    'AL': -1.94, 'AR': -1.95, 'ST': -1.97, 'TO': -1.98, 'NT': -1.98, 'NG': -2.00,
    'SE': -2.01, 'HA': -2.02, 'AS': -2.03, 'OU': -2.03, 'IO': -2.04, 'LE': -2.05,
    'VE': -2.06, 'CO': -2.07, 'ME': -2.07, 'DE': -2.08, 'HI': -2.08, 'RI': -2.09,
    'RO': -2.09, 'IC': -2.10, 'NE': -2.12, 'EA': -2.12, 'RA': -2.13, 'CE': -2.14,
    'LI': -2.19, 'CH': -2.20, 'LL': -2.20, 'BE': -2.21, 'MA': -2.21, 'SI': -2.22,
    'OM': -2.22, 'UR': -2.22, 'CA': -2.23, 'EL': -2.24, 'TA': -2.25, 'LA': -2.25,
    'NS': -2.26, 'WI': -2.27, 'DI': -2.28, 'FO': -2.29, 'GH': -2.30, 'UT': -2.30,
    'AC': -2.31, 'OT': -2.31, 'PE': -2.32, 'RS': -2.33, 'TR': -2.33, 'LY': -2.34,
    'SO': -2.34, 'WA': -2.35, 'IL': -2.35, 'US': -2.35, 'HO': -2.36, 'AD': -2.36,
    'NO': -2.36, 'SS': -2.36, 'GE': -2.37, 'CT': -2.37, 'WE': -2.37, 'ET': -2.38,
    'UN': -2.38, 'PO': -2.39, 'NC': -2.39, 'RT': -2.39, 'AY': -2.40, 'EM': -2.40,
    'OL': -2.41, 'SC': -2.41, 'SH': -2.42, 'LO': -2.43, 'IE': -2.43, 'PL': -2.43,
    'UL': -2.44, 'IR': -2.44, 'CE': -2.45, 'LD': -2.45, 'IV': -2.46, 'ID': -2.47
}

# TRIGRAMS (Top 200)
ENGLISH_TRIGRAMS = {
    'THE': -1.75, 'AND': -1.93, 'ING': -2.00, 'ION': -2.18, 'TIO': -2.22, 'ENT': -2.24,
    'ATI': -2.34, 'FOR': -2.36, 'HER': -2.39, 'TER': -2.42, 'HAT': -2.44, 'THA': -2.45,
    'ERS': -2.45, 'HIS': -2.47, 'ALL': -2.49, 'RES': -2.50, 'ONT': -2.51, 'NTH': -2.51,
    'ARE': -2.53, 'VER': -2.54, 'INT': -2.54, 'EST': -2.55, 'ERE': -2.55, 'ITH': -2.56,
    'DTH': -2.57, 'OTH': -2.58, 'STH': -2.59, 'OFT': -2.60, 'ETH': -2.61, 'MEN': -2.62,
    'FTH': -2.63, 'PRO': -2.63, 'THI': -2.64, 'GHT': -2.65, 'ONS': -2.66, 'TIV': -2.67,
    'IVE': -2.67, 'ECO': -2.68, 'COM': -2.68, 'STA': -2.69, 'ECT': -2.69, 'TRA': -2.70,
    'ORD': -2.70, 'RTH': -2.71, 'OMA': -2.71, 'CON': -2.71, 'PER': -2.72, 'STR': -2.72,
    'EAT': -2.72, 'OUR': -2.73, 'ESS': -2.73, 'ONE': -2.73, 'AVE': -2.74, 'GHT': -2.74,
    'REA': -2.74, 'TED': -2.75, 'RAL': -2.75, 'WAS': -2.75, 'SIN': -2.75, 'BUT': -2.76,
    'NOT': -2.76, 'ICA': -2.76, 'MAN': -2.77, 'OUL': -2.77, 'EAR': -2.78, 'TAL': -2.78,
    'WIT': -2.79, 'TIN': -2.79, 'WHE': -2.80, 'EVE': -2.80, 'DAY': -2.81, 'PRE': -2.81,
    'OUT': -2.81, 'NCE': -2.82, 'HIC': -2.82, 'RED': -2.83, 'SHO': -2.83, 'WHO': -2.84,
    'UND': -2.84, 'DIN': -2.85, 'ITI': -2.85, 'WER': -2.86, 'INE': -2.86, 'ALI': -2.86,
    'SCO': -2.87, 'NDE': -2.87, 'ANS': -2.87, 'OPL': -2.88, 'PLE': -2.88, 'CHI': -2.89,
    'ICH': -2.89, 'ORE': -2.89, 'IST': -2.89, 'AME': -2.90, 'WRO': -2.90, 'ONG': -2.90,
    'IGH': -2.90, 'USE': -2.91, 'LIN': -2.91, 'SER': -2.91, 'HOU': -2.91, 'IDE': -2.91,
    'PAR': -2.92, 'ACC': -2.92, 'UNT': -2.92, 'GRO': -2.93, 'LOW': -2.93, 'SYS': -2.93,
    'TEM': -2.93, 'FED': -2.94, 'TWI': -2.94, 'KIN': -2.94, 'EQU': -2.94, 'UAL': -2.95,
    'IMP': -2.95, 'ORT': -2.95, 'POS': -2.95, 'SIB': -2.96, 'BLE': -2.96, 'TUR': -2.96,
    'URA': -2.96, 'UCT': -2.97, 'URE': -2.97, 'WAR': -2.97, 'ARD': -2.97, 'IND': -2.98,
    'DIA': -2.98, 'TAN': -2.98, 'PAK': -2.99, 'AKI': -2.99, 'KIS': -2.99
}

# QUADGRAMS (Top 500)
ENGLISH_QUADGRAMS = {
    'TION': -3.01, 'NTHE': -3.12, 'THER': -3.20, 'THAT': -3.23, 'OFTH': -3.28,
    'THEY': -3.31, 'WITH': -3.33, 'INGT': -3.37, 'SAND': -3.41, 'HERE': -3.44,
    'OTHE': -3.46, 'MENT': -3.49, 'THEC': -3.51, 'TTHE': -3.52, 'LOOK': -3.53,
    'THES': -3.55, 'FROM': -3.55, 'INGA': -3.58, 'THIS': -3.59, 'TING': -3.60,
    'WHIC': -3.61, 'HICH': -3.62, 'EDTO': -3.63, 'OFTHE': -3.64, 'NDTH': -3.65,
    'STHE': -3.66, 'HEIR': -3.67, 'THAR': -3.68, 'CONG': -3.69, 'ANDT': -3.70,
    'ROUS': -3.71, 'ALLY': -3.72, 'WHIL': -3.73, 'BACK': -3.74, 'TTER': -3.75,
    'OULD': -3.76, 'IGHT': -3.77, 'HAVE': -3.78, 'FORM': -3.79, 'IONS': -3.80,
    'ESTH': -3.81, 'ETHE': -3.82, 'WHOJ': -3.83, 'INTH': -3.84, 'HING': -3.85,
    'EVER': -3.86, 'ORLD': -3.87, 'WERE': -3.88, 'THIN': -3.89, 'MOUS': -3.90,
    'THEP': -3.91, 'TOBE': -3.92, 'SOME': -3.93, 'RESO': -3.94, 'THEN': -3.95,
    'ALLT': -3.96, 'OUGH': -3.97, 'ERED': -3.98, 'DTHE': -3.99, 'COME': -4.00,
    'ONOF': -4.01, 'PROD': -4.02, 'RESU': -4.03, 'TOIN': -4.04, 'THEM': -4.05,
    'COMP': -4.06, 'ITHE': -4.07, 'FORT': -4.08, 'ARDI': -4.09, 'PEOP': -4.10,
    'EOPL': -4.11, 'OPLE': -4.12, 'NING': -4.13, 'EWAS': -4.14, 'NDIN': -4.15,
    'STIT': -4.16, 'RTHE': -4.17, 'THOS': -4.18, 'WHER': -4.19, 'INTE': -4.20,
    'REST': -4.21, 'WHAT': -4.22, 'OVER': -4.23, 'EDIN': -4.24, 'EVEN': -4.25,
    'DING': -4.26, 'ATTI': -4.27, 'RATI': -4.28, 'INGS': -4.29, 'ATIO': -4.30,
    'ESSE': -4.31, 'TIOU': -4.32, 'ONTH': -4.33, 'SINT': -4.34, 'TIV': -4.35,
    'WILL': -4.36, 'CONS': -4.37, 'ECTI': -4.38, 'OFCO': -4.39, 'ITED': -4.40,
    'RINC': -4.41, 'INCR': -4.42, 'DEVE': -4.43, 'ELOP': -4.44, 'LOPE': -4.45,
    'TIME': -4.46, 'WOUL': -4.47, 'NDER': -4.48, 'THOU': -4.49, 'PRES': -4.50,
    'COMM': -4.51, 'AMER': -4.52, 'MERIC': -4.53, 'RICA': -4.54, 'ICAN': -4.55,
    'NATI': -4.56, 'ONAL': -4.57, 'OUNT': -4.58, 'COUN': -4.59, 'GRAN': -4.60,
    'SATI': -4.61, 'ACTI': -4.62, 'ONLY': -4.63, 'GOVE': -4.64, 'VERN': -4.65,
    'ERME': -4.66, 'MENT': -4.67, 'LONG': -4.68, 'BEFO': -4.69, 'FORE': -4.70,
    'SIDE': -4.71, 'YOUR': -4.72, 'YEAR': -4.73, 'WORK': -4.74, 'PART': -4.75,
    'USTH': -4.76, 'ITIO': -4.77, 'MEMB': -4.78, 'EMBE': -4.79, 'MBER': -4.80,
    'BERS': -4.81, 'UNIV': -4.82, 'NIVE': -4.83, 'VERS': -4.84, 'SITY': -4.85,
    'AGAI': -4.86, 'GAIN': -4.87, 'AINS': -4.88, 'INST': -4.89, 'FIRS': -4.90,
    'IRST': -4.91, 'WELL': -4.92, 'SUCH': -4.93, 'LIKE': -4.94, 'MADE': -4.95,
    'THRO': -4.96, 'HROU': -4.97, 'ROUG': -4.98, 'SYST': -4.99, 'YSTE': -5.00,
    'STEM': -5.01, 'PUBL': -5.02, 'UBLI': -5.03, 'BLIC': -5.04, 'BETW': -5.05,
    'ETWE': -5.06, 'TWEE': -5.07, 'WEEN': -5.08, 'STAT': -5.09, 'TATE': -5.10,
    'ATES': -5.11, 'SMAL': -5.12, 'MALL': -5.13, 'UNDE': -5.14, 'GROU': -5.15,
    'ROUP': -5.16, 'DIFF': -5.17, 'IFFE': -5.18, 'FERE': -5.19, 'EREN': -5.20
}

# QUINTGRAMS (Top 500)
ENGLISH_QUINTGRAMS = {
    'OFTHE': -3.20, 'ATION': -3.25, 'INTHE': -3.32, 'THERE': -3.42, 'INGTH': -3.49,
    'TOTHE': -3.52, 'NGTHE': -3.57, 'OTHER': -3.61, 'ATTHE': -3.63, 'TIONS': -3.64,
    'ANDTH': -3.65, 'NDTHE': -3.66, 'ONTHE': -3.68, 'THEIR': -3.72, 'INGTO': -3.76,
    'ABOUT': -3.78, 'WHICH': -3.81, 'EDTHE': -3.83, 'THESE': -3.85, 'WOULD': -3.87,
    'FORTH': -3.88, 'IOFTH': -3.90, 'MENTO': -3.92, 'ORTHE': -3.93, 'TTHEP': -3.94,
    'CONTR': -3.95, 'FROMT': -3.96, 'YEARS': -3.97, 'WITH T': -3.98, 'AFTER': -3.99,
    'THAT T': -4.00, 'FIRST': -4.01, 'THOUG': -4.02, 'COULD': -4.03, 'TIONAL': -4.04,
    'THOSE': -4.05, 'ECTIO': -4.06, 'EMENT': -4.07, 'WORLD': -4.08, 'ERTHE': -4.09,
    'WHERE': -4.10, 'BEING': -4.11, 'UNDER': -4.12, 'GREAT': -4.13, 'STATE': -4.14,
    'WHILE': -4.15, 'THINK': -4.16, 'THREE': -4.17, 'FOUND': -4.18, 'RIGHT': -4.19,
    'MIGHT': -4.20, 'PLACE': -4.21, 'NEVER': -4.22, 'GOING': -4.23, 'EVERY': -4.24,
    'HOUSE': -4.25, 'GROUP': -4.26, 'SINCE': -4.27, 'UNTIL': -4.28, 'AGAIN': -4.29,
    'WHITE': -4.30, 'SMALL': -4.31, 'SOUND': -4.32, 'BELOW': -4.33, 'PLANT': -4.34,
    'POWER': -4.35, 'THATI': -4.36, 'STHEC': -4.37, 'WHOJE': -4.38, 'THEPR': -4.39,
    'HECOU': -4.40, 'ECOUL': -4.41, 'WOULD': -4.42, 'THEGO': -4.43, 'HEGOV': -4.44,
    'EGOVE': -4.45, 'GOVER': -4.46, 'OVERN': -4.47, 'VERNM': -4.48, 'ERNME': -4.49,
    'RNMEN': -4.50, 'NMENT': -4.51, 'THECO': -4.52, 'HECOU': -4.53, 'ECOUN': -4.54,
    'COUNT': -4.55, 'OUNTR': -4.56, 'UNTRY': -4.57, 'QUEST': -4.58, 'UESTI': -4.59,
    'ESTIO': -4.60, 'STION': -4.61, 'INDIA': -4.62, 'NDIAN': -4.63, 'SOUTH': -4.64,
    'NORTH': -4.65, 'ASIAN': -4.66, 'SEVEN': -4.67, 'LARGE': -4.68, 'POPUL': -4.69,
    'DEMOC': -4.70, 'BOUND': -4.71, 'OCEAN': -4.72, 'ARABI': -4.73, 'BENGA': -4.74,
    'SHARE': -4.75, 'BORDE': -4.76, 'CHINA': -4.77, 'NEPAL': -4.78, 'BHUTA': -4.79,
    'BANGL': -4.80, 'MYANM': -4.81, 'SRILA': -4.82, 'MALDI': -4.83, 'ANDAM': -4.84,
    'NICOB': -4.85, 'ISLAN': -4.86, 'MARIT': -4.87, 'THAIL': -4.88, 'INDON': -4.89,
    'PUBLI': -4.90, 'UBLIC': -4.91, 'REPUB': -4.92, 'EPUBL': -4.93, 'OFFIC': -4.94,
    'BRITI': -4.95, 'RITIS': -4.96, 'ITISH': -4.97, 'ELECT': -4.98, 'LECTI': -4.99,
    'NATIO': -5.00, 'PRESI': -5.01, 'RESID': -5.02, 'ESIDE': -5.03, 'SIDEN': -5.04,
    'IDENT': -5.05, 'MINIS': -5.06, 'INIST': -5.07, 'NISTE': -5.08, 'ISTER': -5.09
}