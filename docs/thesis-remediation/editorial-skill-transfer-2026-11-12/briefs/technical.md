# Brief A (technical): blade inspection results
Audience: engineering review board. Deliver a 6-slide deck.
Subject: ultrasonic C-scan versus visual and thermographic inspection of wind-turbine blades (fictional data).
Facts: 240 blades inspected across 4 wind farms in 2025. 31 blades had delamination confirmed by cutting a core sample (ground truth). Probability of detection (POD) by defect length, three methods:
 5 mm: ultrasonic 0.42, visual 0.18, thermography 0.55
 10 mm: ultrasonic 0.88, visual 0.41, thermography 0.90
 20 mm: ultrasonic 0.99, visual 0.77, thermography 0.99
Cost per blade: ultrasonic EUR 410 (3.5 h), visual EUR 60 (0.5 h), thermography EUR 230 (1.5 h; weather dependent, 22 of 240 blades could not be scanned for wind above 8 m/s).
False calls: ultrasonic 6, visual 4, thermography 19. Defects confirmed only after repair opened the blade: 3 (all under 5 mm, none seen by any method).
Recommendation: thermography first on all blades in suitable weather, ultrasonic confirmation on every thermography call and on all blades older than 8 years; keep visual for triage only.
Limits: one blade type (62 m glass fibre), simulated inspection campaign data, confidence intervals not computed for the 5 mm point.
