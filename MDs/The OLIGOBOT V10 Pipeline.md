graph TD
    User[👤 User Message] --> Handlers[📡 Handlers.py]
    
    subgraph "Phase 1: Triage (Intent Manager)"
        Handlers --> Intent{🚦 Detect Intent}
        Intent -- "سلام / خوبی؟" --> Casual[🔵 CASUAL]
        Intent -- "فوتبال / سیاست" --> Irrelevant[🟡 IRRELEVANT]
        Intent -- "آنمی چیست؟" --> Edu[🟣 EDUCATIONAL]
        Intent -- "WBC=15000 / درد سینه" --> Diag[🔴 DIAGNOSTIC]
    end

    subgraph "Phase 2: Protocol (The Professor)"
        Diag --> Extractor[🔍 Extract Entities]
        Extractor --> Memory[(🧠 Case Memory)]
        Memory --> Validator{👮‍♂️ Validate Protocol}
        
        Validator -- "Missing Age/Gender" --> Reject[⛔ STOP & ASK]
        Reject --> User
        
        Validator -- "Data Complete" --> Approved[✅ PROCEED]
    end

    subgraph "Phase 3: Execution (RAG Engine)"
        Casual --> Persona[💬 Persona Reply]
        Irrelevant --> Refusal[🚫 Polite Refusal]
        
        Edu --> RAG[⚙️ RAG Engine]
        Approved --> RAG
        
        RAG --> Search[🔎 Vector Search]
        Search --> Context[📄 Retrieve Docs]
        
        Approved -.-> |Inject Case Summary| Context
        
        Context --> LLM[🤖 Gemini/GPT]
    end

    Persona --> Response[📤 Final Response]
    Refusal --> Response
    LLM --> Response
    Response --> User
