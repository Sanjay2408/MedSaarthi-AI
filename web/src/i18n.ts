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
};

export const SPEECH_LANG: Record<string, string> = { en: "en-IN", hi: "hi-IN", kn: "kn-IN", ta: "ta-IN", te: "te-IN" };
