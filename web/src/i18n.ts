// The words around the plan, in the patient's language, so a Hindi reader is not left
// navigating English. Written by hand, not machine-translated, and included in the
// native-speaker review in docs/EVAL.md. Everything else on this screen stays in English.
export type Words = {
  plan: string; today: string; done: string; markDone: string; of: string; needed: string; noFixed: string;
  nothing: string; howToTake: string; listen: string; stop: string; allDone: string; periods: Record<string, string>;
};

export const WORDS: Record<string, Words> = {
  en: {
    plan: "Your medicine plan", today: "Today", done: "Taken", markDone: "Mark as taken", of: "of", needed: "Only when you need it",
    noFixed: "No fixed time", nothing: "Nothing to take", howToTake: "How to take it", listen: "Listen", stop: "Stop",
    allDone: "That's everything for today.",
    periods: { Morning: "Morning", Afternoon: "Afternoon", Evening: "Evening", Night: "Night" },
  },
  hi: {
    plan: "आपकी दवा की योजना", today: "आज", done: "ले ली", markDone: "ले ली, यह चिह्नित करें", of: "में से", needed: "सिर्फ़ ज़रूरत पड़ने पर",
    noFixed: "कोई तय समय नहीं", nothing: "कोई दवा नहीं", howToTake: "दवा कैसे लें", listen: "सुनें", stop: "रोकें",
    allDone: "आज की सारी दवाएँ हो गईं।",
    periods: { Morning: "सुबह", Afternoon: "दोपहर", Evening: "शाम", Night: "रात" },
  },
  kn: {
    plan: "ನಿಮ್ಮ ಔಷಧಿ ಯೋಜನೆ", today: "ಇಂದು", done: "ತೆಗೆದುಕೊಂಡಿದ್ದೇನೆ", markDone: "ತೆಗೆದುಕೊಂಡಿದ್ದೇನೆ ಎಂದು ಗುರುತಿಸಿ", of: "ರಲ್ಲಿ", needed: "ಅಗತ್ಯವಿದ್ದಾಗ ಮಾತ್ರ",
    noFixed: "ನಿಗದಿತ ಸಮಯವಿಲ್ಲ", nothing: "ಯಾವ ಔಷಧಿಯೂ ಇಲ್ಲ", howToTake: "ಹೇಗೆ ತೆಗೆದುಕೊಳ್ಳಬೇಕು", listen: "ಕೇಳಿ", stop: "ನಿಲ್ಲಿಸಿ",
    allDone: "ಇಂದಿನ ಎಲ್ಲಾ ಔಷಧಿಗಳು ಮುಗಿದಿವೆ.",
    periods: { Morning: "ಬೆಳಿಗ್ಗೆ", Afternoon: "ಮಧ್ಯಾಹ್ನ", Evening: "ಸಂಜೆ", Night: "ರಾತ್ರಿ" },
  },
  ta: {
    plan: "உங்கள் மருந்துத் திட்டம்", today: "இன்று", done: "எடுத்துவிட்டேன்", markDone: "எடுத்துவிட்டதாகக் குறிக்கவும்", of: "இல்", needed: "தேவைப்படும்போது மட்டும்",
    noFixed: "நிர்ணயித்த நேரம் இல்லை", nothing: "மருந்து இல்லை", howToTake: "எப்படி எடுப்பது", listen: "கேளுங்கள்", stop: "நிறுத்து",
    allDone: "இன்றைய எல்லா மருந்துகளும் முடிந்தன.",
    periods: { Morning: "காலை", Afternoon: "மதியம்", Evening: "மாலை", Night: "இரவு" },
  },
  te: {
    plan: "మీ మందుల ప్రణాళిక", today: "ఈ రోజు", done: "తీసుకున్నాను", markDone: "తీసుకున్నట్లు గుర్తించండి", of: "లో", needed: "అవసరమైనప్పుడు మాత్రమే",
    noFixed: "నిర్ణీత సమయం లేదు", nothing: "మందులు లేవు", howToTake: "ఎలా తీసుకోవాలి", listen: "వినండి", stop: "ఆపండి",
    allDone: "ఈ రోజు మందులన్నీ అయిపోయాయి.",
    periods: { Morning: "ఉదయం", Afternoon: "మధ్యాహ్నం", Evening: "సాయంత్రం", Night: "రాత్రి" },
  },
  bn: {
    plan: "আপনার ওষুধের পরিকল্পনা", today: "আজ", done: "খেয়েছি", markDone: "খেয়েছি বলে চিহ্নিত করুন", of: "এর মধ্যে", needed: "শুধু প্রয়োজন হলে",
    noFixed: "কোনো নির্দিষ্ট সময় নেই", nothing: "কোনো ওষুধ নেই", howToTake: "কীভাবে নেবেন", listen: "শুনুন", stop: "থামান",
    allDone: "আজকের সব ওষুধ শেষ।",
    periods: { Morning: "সকাল", Afternoon: "দুপুর", Evening: "সন্ধ্যা", Night: "রাত" },
  },
  mr: {
    plan: "तुमची औषध योजना", today: "आज", done: "घेतले", markDone: "घेतले म्हणून नोंद करा", of: "पैकी", needed: "फक्त गरज असेल तेव्हा",
    noFixed: "ठरलेली वेळ नाही", nothing: "कोणतेही औषध नाही", howToTake: "कसे घ्यावे", listen: "ऐका", stop: "थांबवा",
    allDone: "आजची सर्व औषधे घेऊन झाली.",
    periods: { Morning: "सकाळ", Afternoon: "दुपार", Evening: "संध्याकाळ", Night: "रात्र" },
  },
  gu: {
    plan: "તમારી દવાની યોજના", today: "આજે", done: "લીધી", markDone: "લીધી તરીકે નોંધો", of: "માંથી", needed: "જરૂર પડે ત્યારે જ",
    noFixed: "કોઈ નક્કી સમય નથી", nothing: "કોઈ દવા નથી", howToTake: "કેવી રીતે લેવી", listen: "સાંભળો", stop: "બંધ કરો",
    allDone: "આજની બધી દવાઓ લેવાઈ ગઈ.",
    periods: { Morning: "સવાર", Afternoon: "બપોર", Evening: "સાંજ", Night: "રાત" },
  },
  ml: {
    plan: "നിങ്ങളുടെ മരുന്ന് പദ്ധതി", today: "ഇന്ന്", done: "കഴിച്ചു", markDone: "കഴിച്ചതായി രേഖപ്പെടുത്തുക", of: "ൽ", needed: "ആവശ്യമുള്ളപ്പോൾ മാത്രം",
    noFixed: "നിശ്ചിത സമയമില്ല", nothing: "മരുന്നൊന്നുമില്ല", howToTake: "എങ്ങനെ ഉപയോഗിക്കണം", listen: "കേൾക്കുക", stop: "നിർത്തുക",
    allDone: "ഇന്നത്തെ എല്ലാ മരുന്നുകളും കഴിഞ്ഞു.",
    periods: { Morning: "രാവിലെ", Afternoon: "ഉച്ച", Evening: "വൈകുന്നേരം", Night: "രാത്രി" },
  },
  pa: {
    plan: "ਤੁਹਾਡੀ ਦਵਾਈ ਦੀ ਯੋਜਨਾ", today: "ਅੱਜ", done: "ਲੈ ਲਈ", markDone: "ਲੈ ਲਈ ਵਜੋਂ ਦਰਜ ਕਰੋ", of: "ਵਿੱਚੋਂ", needed: "ਸਿਰਫ਼ ਲੋੜ ਪੈਣ 'ਤੇ",
    noFixed: "ਕੋਈ ਪੱਕਾ ਸਮਾਂ ਨਹੀਂ", nothing: "ਕੋਈ ਦਵਾਈ ਨਹੀਂ", howToTake: "ਕਿਵੇਂ ਲੈਣੀ ਹੈ", listen: "ਸੁਣੋ", stop: "ਰੋਕੋ",
    allDone: "ਅੱਜ ਦੀਆਂ ਸਾਰੀਆਂ ਦਵਾਈਆਂ ਹੋ ਗਈਆਂ।",
    periods: { Morning: "ਸਵੇਰ", Afternoon: "ਦੁਪਹਿਰ", Evening: "ਸ਼ਾਮ", Night: "ਰਾਤ" },
  },
  od: {
    plan: "ଆପଣଙ୍କ ଔଷଧ ଯୋଜନା", today: "ଆଜି", done: "ନେଇଛି", markDone: "ନେଇଛି ବୋଲି ଚିହ୍ନଟ କରନ୍ତୁ", of: "ରୁ", needed: "କେବଳ ଆବଶ୍ୟକ ହେଲେ",
    noFixed: "କୌଣସି ନିର୍ଦ୍ଦିଷ୍ଟ ସମୟ ନାହିଁ", nothing: "କୌଣସି ଔଷଧ ନାହିଁ", howToTake: "କିପରି ନେବେ", listen: "ଶୁଣନ୍ତୁ", stop: "ବନ୍ଦ କରନ୍ତୁ",
    allDone: "ଆଜିର ସବୁ ଔଷଧ ସରିଗଲା।",
    periods: { Morning: "ସକାଳ", Afternoon: "ଦିପହର", Evening: "ସନ୍ଧ୍ୟା", Night: "ରାତି" },
  },
};

export const SPEECH_LANG: Record<string, string> = {
  en: "en-IN", hi: "hi-IN", kn: "kn-IN", ta: "ta-IN", te: "te-IN", bn: "bn-IN", mr: "mr-IN", gu: "gu-IN", ml: "ml-IN", pa: "pa-IN", od: "or-IN",
};

/** The pack code for Odia is "od"; HTML and speech engines know the language as "or". */
export const htmlLang = (code: string) => (code === "od" ? "or" : code);
