"""Vocabulary for the synthetic prescription generator.

Everything here was written by hand from common knowledge of generic medicine names used in
India. It is NOT copied from the A-Z Medicine Dataset or any other file, so it can be committed.
Names are real generic or brand names used only as strings; strengths are plausible, not clinical
guidance. Nothing here is a dosing recommendation.
"""

GENERICS = """
paracetamol ibuprofen diclofenac aceclofenac naproxen tramadol etoricoxib nimesulide ketorolac
amoxicillin co-amoxiclav azithromycin clarithromycin erythromycin doxycycline ciprofloxacin
levofloxacin ofloxacin moxifloxacin cefixime cefpodoxime cefuroxime ceftriaxone cefadroxil
cephalexin metronidazole tinidazole ornidazole nitrofurantoin cotrimoxazole linezolid rifampicin
isoniazid pyrazinamide ethambutol fluconazole itraconazole terbinafine clotrimazole acyclovir
valacyclovir oseltamivir ivermectin albendazole mebendazole praziquantel chloroquine
hydroxychloroquine primaquine artemether metformin glimepiride gliclazide glipizide sitagliptin
vildagliptin teneligliptin linagliptin pioglitazone empagliflozin dapagliflozin amlodipine
telmisartan losartan olmesartan valsartan ramipril enalapril lisinopril atenolol metoprolol
bisoprolol carvedilol propranolol nebivolol hydrochlorothiazide chlorthalidone furosemide
torsemide spironolactone clonidine nifedipine diltiazem verapamil isosorbide nitroglycerin
atorvastatin rosuvastatin simvastatin fenofibrate aspirin clopidogrel prasugrel ticagrelor
warfarin rivaroxaban apixaban digoxin amiodarone ranitidine famotidine omeprazole pantoprazole
esomeprazole rabeprazole lansoprazole domperidone ondansetron metoclopramide loperamide
racecadotril lactulose bisacodyl drotaverine hyoscine mebeverine cetirizine levocetirizine
fexofenadine loratadine chlorpheniramine montelukast salbutamol levosalbutamol ipratropium
tiotropium formoterol budesonide fluticasone theophylline ambroxol bromhexine dextromethorphan
guaifenesin prednisolone methylprednisolone dexamethasone hydrocortisone deflazacort
levothyroxine carbimazole methimazole alendronate calcium cholecalciferol folic-acid
ferrous-sulphate cyanocobalamin methylcobalamin ascorbic-acid zinc-sulphate pregabalin
gabapentin amitriptyline nortriptyline duloxetine sertraline escitalopram fluoxetine paroxetine
mirtazapine venlafaxine alprazolam clonazepam lorazepam diazepam zolpidem melatonin
levetiracetam phenytoin carbamazepine valproate lamotrigine topiramate oxcarbazepine haloperidol
risperidone olanzapine quetiapine aripiprazole lithium donepezil memantine levodopa pramipexole
ropinirole tamsulosin finasteride dutasteride silodosin sildenafil tadalafil oxybutynin
solifenacin mirabegron allopurinol febuxostat colchicine methotrexate leflunomide sulfasalazine
azathioprine mycophenolate tacrolimus cyclosporine tranexamic-acid norethisterone progesterone
letrozole clomiphene tamoxifen anastrozole
""".split()

BRANDS = """
Crocin Dolo Calpol Brufen Combiflam Voveran Zerodol Augmentin Azithral Zithromax Taxim Pantocid
Pan Nexpro Razo Omez Digene Gelusil Allegra Montair Levocet Okacet Glycomet Glyciphage Amaryl
Januvia Telma Telsartan Amlokind Stamlo Ecosprin Clopilet Storvas Atorva Rosuvas Thyronorm
Eltroxin Shelcal Neurobion Becosules Limcee Zincovit Liv52 Cheston Sinarest Benadryl Ascoril
Corex Asthalin Foracort Seroflo Duolin Cipla Wysolone Deflaza Lasix Aldactone Dytor Ciplox
Norflox Oflox Metrogyl Flagyl Zifi Cefakind Mox Novamox Althrocin Doxy Ondem Emeset Vomikind
Rantac Zinetac Cyclopam Meftal Nise Pregalin Gabapin Nexito Cipralex Restyl Alprax Clonotril
""".split()

FORMS = ["Tab.", "Tab", "T.", "Cap.", "Cap", "C.", "Syp.", "Syp", "Inj.", "Inh.", "Tablet", "Capsule", "Eye drops", "Oint.", "Drops"]
FORM_ROUTE = {"Tab.": "oral", "Tab": "oral", "T.": "oral", "Cap.": "oral", "Cap": "oral", "C.": "oral", "Syp.": "oral", "Syp": "oral",
              "Tablet": "oral", "Capsule": "oral", "Inj.": "injection", "Inh.": "inhalation", "Eye drops": "eye", "Oint.": "topical",
              "Drops": "oral"}

STRENGTHS = {
    "paracetamol": ["325 mg", "500 mg", "650 mg", "1000 mg"], "ibuprofen": ["200 mg", "400 mg", "600 mg"],
    "amoxicillin": ["250 mg", "500 mg", "875 mg"], "azithromycin": ["250 mg", "500 mg"],
    "metformin": ["250 mg", "500 mg", "850 mg", "1000 mg"], "amlodipine": ["2.5 mg", "5 mg", "10 mg"],
    "atorvastatin": ["10 mg", "20 mg", "40 mg"], "pantoprazole": ["20 mg", "40 mg"], "cetirizine": ["5 mg", "10 mg"],
    "salbutamol": ["100 mcg", "200 mcg"], "levothyroxine": ["25 mcg", "50 mcg", "100 mcg"], "ondansetron": ["4 mg", "8 mg"],
    "telmisartan": ["20 mg", "40 mg", "80 mg"], "losartan": ["25 mg", "50 mg"], "aspirin": ["75 mg", "150 mg"],
    "clopidogrel": ["75 mg"], "prednisolone": ["5 mg", "10 mg", "20 mg"], "montelukast": ["5 mg", "10 mg"],
}
DEFAULT_STRENGTHS = ["5 mg", "10 mg", "20 mg", "25 mg", "40 mg", "50 mg", "100 mg", "150 mg", "200 mg", "250 mg", "500 mg", "1 g"]
LIQUID_DOSES = ["2.5 ml", "5 ml", "10 ml", "15 ml"]

FREQUENCIES = [
    ("OD", 10), ("BD", 10), ("TDS", 10), ("QID", 4), ("HS", 6), ("SOS", 5), ("STAT", 2), ("BID", 2), ("TID", 2), ("QD", 1),
    ("1-0-1", 8), ("1-1-1", 7), ("0-0-1", 5), ("1-0-0", 5), ("0-1-0", 3), ("1-1-0", 2), ("0-1-1", 2), ("1-1-1-1", 1),
    ("once daily", 4), ("twice daily", 4), ("three times a day", 3), ("once a day", 3), ("twice a day", 3),
    ("every 8 hours", 3), ("every 6 hours", 3), ("every 12 hours", 3), ("q8h", 1), ("q12h", 1), ("3 times a day", 2),
    ("at bedtime", 2), ("morning", 1), ("at night", 2), ("daily", 2),
]
DURATIONS = [
    "1 day", "2 days", "3 days", "4 days", "5 days", "7 days", "10 days", "14 days", "15 days", "21 days", "30 days", "60 days", "90 days",
    "1 week", "2 weeks", "3 weeks", "1 month", "2 months", "3 months", "5 d", "7 d", "10 d", "5/7", "3/7", "10/7", "14/7", "1/52", "2/52",
]
INSTRUCTIONS = [
    "after food", "before food", "after meals", "before meals", "with food", "with water", "with milk", "on empty stomach",
    "at bedtime", "in the morning", "before breakfast", "after breakfast", "after dinner", "one hour before food", "half an hour before food",
    "for fever", "for pain", "if needed", "when breathless", "for cough", "in both eyes", "in the left eye", "in the right eye",
    "apply thinly", "do not crush", "swallow whole", "avoid alcohol", "avoid driving", "shake well", "gargle after use", "rinse mouth after use",
]
CONNECTORS = ["x ", "x", "X ", "for ", "for", "", "", "x "]
FIRST = ["Aarav", "Diya", "Kavya", "Rohan", "Meera", "Arjun", "Isha", "Vikram", "Anaya", "Sanjay", "Lakshmi", "Farhan", "Priya", "Nikhil", "Sunita"]
LAST = ["Sharma", "Reddy", "Nair", "Iyer", "Khan", "Patel", "Gowda", "Das", "Rao", "Menon", "Singh", "Joshi", "Kulkarni", "Shetty"]
