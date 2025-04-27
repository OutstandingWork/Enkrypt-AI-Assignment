graph TD
    %% Main Application Structure
    A[main.py] --> B[Flask App Initialization]
    B --> C[Register Routes]
    
    %% Core Components - Grouped logically
    subgraph CoreComponents
        D[routes.py]
        P[SessionManager]
        Q[BookingDatabase]
        R[GroqHandler]
    end
    
    C --> D
    
    %% Routes - Grouped together
    subgraph APIRoutes
        E[Index Route]
        F[Booking Route]
        G[Available Slots Route]
        H[User Bookings Route]
        I[Cancel Booking Route]
        J[Reset Bookings Route]
    end
    
    D --> E
    D --> F
    D --> G
    D --> H
    D --> I
    D --> J
    
    %% Booking Process Flow - Logical sequence
    F --> K[process_booking_request]
    K --> L[GroqHandler.parse_user_intent]
    
    %% Intent Processing - Grouped by intent type
    subgraph IntentProcessing
        M[Booking Intent]
        N[Cancellation Intent]
        O[Availability Intent]
    end
    
    L --> M
    L --> N
    L --> O
    
    %% Session Management - All related functions together
    subgraph SessionManagement
        P1[New Session]
        P2[Retrieve Session]
        P3[Update Context]
        P4[Add Conversation]
        P5[Store Booking Info]
    end
    
    K --> P
    P --> P1
    P --> P2
    P --> P3
    P --> P4
    P --> P5
    
    %% Database Operations - All DB functions together
    subgraph DatabaseOperations
        Q1[Create Booking]
        Q2[Remove Booking]
        Q3[List Available Times]
        Q4[User History]
        Q5[Read CSV]
        Q6[Write CSV]
    end
    
    M --> Q
    N --> Q
    O --> Q
    Q --> Q1
    Q --> Q2
    Q --> Q3
    Q --> Q4
    Q --> Q5
    Q --> Q6
    
    %% LLM Integration - All LLM functions together
    subgraph LLMIntegration
        R1[Format Booking Response]
        R2[Format Cancellation Response]
        R3[Format Available Slots]
        R4[Resolve Festival Dates]
    end
    
    M --> R
    N --> R
    O --> R
    R --> R1
    R --> R2
    R --> R3
    R --> R4
    
    %% Date and Time Handling - Grouped together
    subgraph DateProcessing
        S[Date Utilities]
        S1[Parse Natural Language Dates]
        S2[Resolve Festival Dates]
    end
    
    M --> S
    S --> S1
    S --> S2
    
    %% Data Models - Grouped together
    subgraph DataModels
        T[Models]
        T1[Booking Model]
        T2[Slot Model]
    end
    
    Q1 --> T
    T --> T1
    T --> T2
    
    %% Data Storage - Grouped together
    subgraph DataStorage
        U[Data Files]
        U1[Booking Records CSV]
        U2[Session JSON Files]
    end
    
    Q5 --> U
    Q6 --> U
    U --> U1
    P1 --> U2
    P2 --> U2
    
    %% Utilities - Grouped together
    subgraph Utilities
        V[Utility Functions]
        V1[Validate Input]
        V2[Date Conversion]
        V3[Format Validation]
    end
    
    K --> V
    V --> V1
    V --> V2
    V --> V3
    
    %% External APIs - Grouped together and properly connected
    subgraph ExternalAPIs
        W[API Connections]
        W1[Groq LLM API]
        W2[Calendarific API]
    end
    
    R --> W
    W --> W1
    S2 --> W2
    
    %% Frontend - Grouped together
    subgraph Frontend
        Z1[HTML Templates]
        Z2[JavaScript Client]
        Z3[User Interface]
    end
    
    E --> Z1
    Z1 --> Z2
    Z2 --> Z3
    Z3 --> F
    Z3 --> G
    Z3 --> H
    Z3 --> I
    
    %% Connections between major components
    K --> R
    K --> P
    K --> Q
    
    %% Styling
    classDef core fill:#f9f,stroke:#333,stroke-width:2px
    classDef route fill:#bbf,stroke:#333,stroke-width:1px
    classDef data fill:#bfb,stroke:#333,stroke-width:1px
    classDef api fill:#fbb,stroke:#333,stroke-width:1px
    
    class A,B,C core
    class E,F,G,H,I,J route
    class Q,U,P data
    class R,W api![image](https://github.com/user-attachments/assets/7f9f57a3-7b72-4e21-98a9-ce6ea46e642c)
