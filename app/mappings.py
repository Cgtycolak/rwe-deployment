# Plant mappings for different types of power plants

plant_mapping = {
    'plant_names': [
        "ACWA", "AKENRJ ERZIN", "AKSA ANT", "BAN1", "BAN2", "BAYMINA", 
        "BILGIN1", "BILGIN2", "BURSA BLOK1", "BURSA BLOK2", "CENGIZ",
        "ENKA ADP", "ENKA GBZ1", "ENKA GBZ2", "ENKA IZM1", "ENKA IZM2",
        "GAMA ICAN", "HABAS", "HAM-10", "HAM-20", "RWE", "TEKİRA",
        "TEKİRB", "YENI", "İST A-(A)", "İST A-(B)", "İST A-(C)",
        "İST B (Blok40+ Blok50)"
    ],
    'o_ids': [
        10372, 166, 396, 282, 282, 11816, 294, 294, 195, 195, 1964,
        11810, 11811, 11811, 11997, 11997, 9488, 181, 378, 378, 3625,
        195, 195, 6839, 195, 195, 195, 195
    ],
    'uevcb_ids': [
        3197267, 3205710, 134405, 24604, 3194367, 3205527, 3204758, 3204759,
        924, 928, 1740316, 3205381, 3205524, 3205525, 3206732, 3206733,
        3195727, 2543, 945, 983, 301420, 3204400, 3204399, 472111, 923,
        979, 980, 937
    ],
    'p_ids': [
        2170, 1673, 754, 1426, 2045, 893, 869, 869, 687, 687, 2334, 2800, 
        661, 661, 962, 962, 2048, 2411, 1113, 1113, 966, 1112, 1224, 1424, 
        1230, 1230, 1230, 638 
    ],
    'capacities': [
        "927", "904", "900", "935", "607", "770", "443", "443", "680",
        "680", "610", "820", "815", "815", "760", "760", "853", "1043",
        "600", "600", "797", "480", "480", "480", "450", "450", "450", "816"
    ],
}

import_coal_mapping = {
    'plant_names': [
        "ZETES 1", "ZETES 2-A", "ZETES 2-B", "ZETES 3-A", "ZETES 3-B", "HUNUTLU TES_TR1", 
        "HUNUTLU TES_TR2", "CENAL TES(TR1+TRA)", "CENAL TES(TR2)", "İSKENDERUN İTHAL KÖMÜR SANTRALI-2", 
        "İSKENDERUN İTHAL KÖMÜR SANTRALI-1", "ATLAS TES", "İÇDAŞ BEKİRLİ 1", "İÇDAŞ BEKİRLİ 2", "İÇDAŞ BİGA TERMİK SANTRALİ_1",
        "İÇDAŞ BİGA TERMİK SANTRALİ_2", "İÇDAŞ BİGA TERMİK SANTRALİ_3", "İZDEMİR ENERJİ", "ÇOLAKOĞLU OP-2 SANTRALİ"
    ],
    'o_ids': [
        603, 603, 603, 603, 603, 18921, 18921, 11033, 11033, 13257, 13257, 7639,
        4831, 4831, 369, 369, 369, 6999, 149
    ],
    'uevcb_ids': [
        18588, 25501, 28365, 3196007, 3196567, 3220150, 3221490, 3200210, 
        3217890, 3208212, 3208213, 1478766, 61976, 1542318, 2728, 4054, 4136, 952237, 3718
    ],
    'capacities': [
        "2790", "2790", "2790", "2790", "2790", "1320", "1320 ", "1320", "1320", "1308", "1308",
        "1260", "1260", "1200", " 1200", "1200", "405", "370", "190"
    ],
    'p_ids': []
}

hydro_mapping = {
    'plant_names': [
        "ATATÜRK HES DB", "KARAKAYAHES1-6", "KEBAN HES 1-8", "ILISU BARAJI ve HES", "ALTINKAYA 1-4", 
        "BİRECİK-NİZİP BARAJI ve HES", "DERİNER HES", "YEDİSU HES", "BEYHAN-1", "YUSUFELI BARAJI VE HES", 
        "OYMAPINAR HES", "BOYABAT HES", "BERKE HES DB", "AŞAĞI KALEKÖY BARAJI ve HES", "H.UĞURLU 1-4",
        "ÇETİN BARAJI ve HES", "ARTVİN BARAJI ve HES", "YEDİGÖZE HES", "ERMENEK HES1", "BORÇKA HES DB"
    ],
    'o_ids': [
        195, 195, 195, 195, 195, 
        195, 195, 4872, 8243, 195, 
        134, 5634, 195, 12897, 195,
        3834, 9422, 5650, 195, 195
    ],
    'uevcb_ids': [
        733, 736, 744, 3211210, 801,
        3196807, 335652, 83087, 2454986, 5000860, 
        2415, 111617, 777, 3208350, 807,
        3209498, 3194434, 26648, 111619, 3692
    ],
    'p_ids': [
        641, 986, 979, 2543, 650,
        978, 1570, 2302, 1849, 3056,
        878, 864, 1074, 2531, 863,
        2537, 1974, 1185, 947, 1278
    ],
    'capacities': [
        "2.405", "1.800", "1.330", "1.208", "702", 
        "672", "670", "627", "582", "548", 
        "540", "513", "510",  "500", "500", 
        "420", "332", "311", "302", "301"
    ]
} 