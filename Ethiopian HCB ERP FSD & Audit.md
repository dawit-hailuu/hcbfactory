# **Functional Specification Document: Audit-Ready Hollow Concrete Block Manufacturing ERP System for Addis Ababa, Ethiopia**

## **System Integration and Architectural Overview**

Executing a scalable, audit-ready hollow concrete block (HCB) manufacturing operation within the Addis Ababa municipal boundary requires integrating physical inventory movements, industrial batching systems, and Ministry of Revenues (MoR) fiscal compliance standards.  
The manufacturing process must manage raw bulk commodities—including bulk cement (Grades 42.5R and 32.5N) 1, crushed stone aggregate grades (01, 02, and sand), volcanic scoria (red ash) from regional quarries such as Meti 1, lightweight pumice, and water trucked from private municipal boreholes—and track them through production, curing, and sales.  
The enterprise resource planning (ERP) system (e.g., SAP S/4HANA, Odoo Enterprise v17, or ERPNext v15) must serve as the single source of truth. Every transaction, from inbound bulk weighing to the final outbound gate pass (ይለፍ), must be recorded.3  
The database enforces a strict state machine across all documents:  
![][image1]  
For compliance with MoR regulations, the system must integrate with the tax authority's systems.5 Under Ministry of Revenues Directive No. 188/2024 and Directive No. 1099/2025, every tax invoice must feature a unique, government-generated identification QR code.5 This QR code, measuring at least 2 cm x 2 cm, must be printed on the top-right header using penetrating ink on security paper printed by authorized state-run enterprises like Berhanena Selam.5  
Receipts issued without this unique code are invalid, resulting in the rejection of VAT deductions and business expense claims.7  
Furthermore, the system must enforce strict withholding tax (WHT) rules: 2% for registered suppliers 9, 30% punitive withholding for unregistered vendors 10, and a 3% rate under Directive 2/2018 for informal transactions recorded with a Purchase Voucher 10, up to a strict annual ceiling of 2,000,000 ETB.10  
The following sections define the transaction vouchers, slips, notes, and records required for each module.

## **Module 1: Inbound Logistics and Procurement**

The raw material supply chain of a hollow concrete block (HCB) manufacturing plant relies on high-volume bulk commodities.  
To maintain strict regulatory compliance with the MoR and prevent financial leaks, every physical entry of material must be matched with its digital equivalent in the ERP system.6  
The transition from physical receipt to financial booking is controlled by standard guidelines, adapted for industrial ERPs via the Model 19 Store Receipt Voucher (SRV).3

### **1\. Inbound Weighbridge Ticket (የገቢ ሚዛን ቲኬት)**

The primary document that captures the raw physical weight of incoming bulk materials prior to offloading in the yard.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Inbound Weighbridge Ticket / የገቢ ሚዛን ቲኬት |
| **Exact Trigger Event** | Physical positioning of a loaded delivery truck on the inbound yard scale, prompting the load cell sensors to trigger a weight capture in the ERP Weighbridge Module. |
| **Complete Mandatory Fields** | ticket\_uuid (UUID), truck\_plate\_no (VARCHAR), trailer\_plate\_no (VARCHAR), driver\_name (VARCHAR), driver\_license\_no (VARCHAR), supplier\_tin (VARCHAR), supplier\_name (VARCHAR), material\_type (ENUM: Cement-42.5R, Cement-32.5N, Aggregate-01, Aggregate-02, Sand, Red-Ash, Pumice, Water), gross\_weight\_kg (DECIMAL), tare\_weight\_kg (DECIMAL), net\_weight\_kg (DECIMAL), scale\_operator\_id (INT), weighbridge\_id (VARCHAR), timestamp\_in (DATETIME). |
| **Approval Workflow** | Scale Operator (Originator) ![][image2] Yard Supervisor (Verifier) ![][image2] Inventory Controller (Approver). |
| **Accounting/Inventory Impact** | No financial posting. Inventory location shift: Material is placed in a virtual In-Transit/Weighbridge Yard location, pending physical QA inspection and offloading. |

### **2\. Material Inspection & QA Lab Slip (የዕቃ ፍተሻ እና የላብራቶሪ ሰነድ)**

This document records the physical and chemical verification of incoming raw materials to prevent sub-standard components from entering the batching plant.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Material Inspection and Quality Assurance Lab Slip / የዕቃ ፍተሻ እና የላብራቶሪ ሰነድ |
| **Exact Trigger Event** | Completion of bulk unloading at the designated stockpiles, prompting the lab technician to sample the batch and log the test results in the ERP Quality Module. |
| **Complete Mandatory Fields** | qa\_test\_id (UUID), weighbridge\_ticket\_ref (UUID), material\_type (ENUM), silt\_content\_pct (DECIMAL; mandatory for sand, threshold \< 6.0%), moisture\_content\_pct (DECIMAL; used for sand/scoria batching correction), sieve\_analysis\_ref (VARCHAR), visual\_impurities (BOOLEAN), qa\_status (ENUM: Approved, Rejected, Quarantine), lab\_tech\_id (INT), timestamp\_test (DATETIME). |
| **Approval Workflow** | Materials Lab Technician (Originator) ![][image2] Quality Control Lead (Verifier) ![][image2] Plant Manager (Approver). |
| **Accounting/Inventory Impact** | Non-financial. The material status in the inventory system updates from Pending QA to either Approved for Production or Rejected/Quarantine. |

### **3\. Store Receipt Voucher (Model 19\) (የዕቃ ገቢ ማድረጊያ ሰነድ \- ሞዴል 19\)**

The Model 19 is the official proof of receipt of inventory into the physical warehouses and stockpiles, serving as the basis for invoice matching.3

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Store Receipt Voucher (Model 19\) / የዕቃ ገቢ ማድረጊያ ሰነድ (ሞዴል 19\) 3 |
| **Exact Trigger Event** | System transition of a Material Inspection Slip to "Approved" status, coupled with physical offloading confirmation by the storekeeper. |
| **Complete Mandatory Fields** | model\_19\_serial (VARCHAR; pre-printed MoR series), supplier\_tin (VARCHAR), supplier\_name (VARCHAR), purchase\_order\_ref (UUID), item\_code (VARCHAR), item\_description (VARCHAR), accepted\_quantity (DECIMAL), uom (ENUM: Metric-Tons, Bags, Liters), unit\_cost\_etb (DECIMAL), total\_value\_etb (DECIMAL), storekeeper\_digital\_sig (BLOB), storage\_location\_id (VARCHAR), distribution\_flags (original to Accounts, 2nd to Receiver, 3rd to Stock Card, 4th to Pad).3 |
| **Approval Workflow** | Receiving Storekeeper (Originator) ![][image2] Warehouse Supervisor (Verifier) ![][image2] Finance Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: Raw Materials Inventory Asset Account (GL-1102) \[by total value\]; Credit: Inventory Received But Not Invoiced (IRNI) Clearing Account (GL-2105). Stock balance increases in the main storage location. |

### **4\. Supplier Purchase Invoice (የዕቃ ግዢ ደረሰኝ)**

The formal billing document sent by the supplier, which must be matched with the physical receipts before payment can be authorized.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Supplier Purchase Invoice / የአቅራቢ የግብር ደረሰኝ 12 |
| **Exact Trigger Event** | Receipt of the vendor’s commercial tax invoice, matched with a corresponding Model 19 Store Receipt Voucher in the ERP Accounts Payable module.3 |
| **Complete Mandatory Fields** | invoice\_uuid (UUID), supplier\_invoice\_no (VARCHAR), supplier\_name (VARCHAR), supplier\_tin (VARCHAR), supplier\_vat\_no (VARCHAR), buyer\_tin (VARCHAR; plant's TIN), model\_19\_ref (VARCHAR) 3, issue\_date (DATE), subtotal\_etb (DECIMAL), vat\_15\_etb (DECIMAL) 12, total\_gross\_etb (DECIMAL) 12, mor\_invoice\_qr\_code (BLOB; 2 cm x 2 cm right-header QR verification from MoR).5 |
| **Approval Workflow** | Accounts Payable Clerk (Originator) ![][image2] AP Accountant (Verifier) ![][image2] Finance Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: IRNI Clearing Account (GL-2105), Debit: VAT Input Receivable Account (GL-1108); Credit: Accounts Payable (GL-2101). |

### **5\. 2% Withholding Tax Voucher (የ2% ታክስ መያዣ ደረሰኝ)**

This document records the mandatory tax withheld at source for transactions exceeding 10,000 ETB with registered suppliers.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Withholding Tax Voucher (2%) / የ2% ታክስ መያዣ ደረሰኝ 9 |
| **Exact Trigger Event** | Validation and posting of a formal Supplier Purchase Invoice exceeding the statutory threshold of 10,000 ETB in a single transaction.9 |
| **Complete Mandatory Fields** | wht\_2\_voucher\_no (VARCHAR; system-generated MoR sequence), date\_of\_issue (DATE), supplier\_name (VARCHAR), supplier\_tin (VARCHAR), base\_invoice\_amount\_etb (DECIMAL; excluding VAT), wht\_rate\_pct (DECIMAL; constant 2.0%) 9, withheld\_amount\_etb (DECIMAL; 2% of base) 9, net\_payable\_to\_supplier (DECIMAL), compliance\_accountant\_id (INT). |
| **Approval Workflow** | Tax Compliance Clerk (Originator) ![][image2] Senior Tax Accountant (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Debit: Accounts Payable (GL-2101); Credit: Withholding Tax Payable \- 2% (GL-2109). |

### **6\. 30% Punitive Withholding Tax Voucher (የ30% ታክስ መያዣ ደረሰኝ)**

This voucher enforces tax deductions for unregistered vendors who do not possess a renewed trade license or a Tax Identification Number (TIN).10

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Punitive Withholding Tax Voucher (30%) / የ30% ታክስ መያዣ ደረሰኝ 10 |
| **Exact Trigger Event** | System entry of a purchase transaction from a vendor lacking a valid trade license and TIN, where the transaction value exceeds 10,000 ETB.10 |
| **Complete Mandatory Fields** | wht\_30\_voucher\_no (VARCHAR), supplier\_name (VARCHAR), supplier\_national\_id (VARCHAR), base\_invoice\_amount\_etb (DECIMAL), wht\_rate\_pct (DECIMAL; constant 30.0%) 10, withheld\_amount\_etb (DECIMAL; 30% of base) 10, net\_cash\_paid\_etb (DECIMAL), auditor\_validation\_sig (BLOB). |
| **Approval Workflow** | Procurement Clerk (Originator) ![][image2] Tax Compliance Lead (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Debit: Accounts Payable (GL-2101); Credit: Withholding Tax Payable \- 30% (GL-2110). |

### **7\. 3% Purchase Voucher (የውስጥ መግዣ ሰነድ \- 3% ዊዝሆልዲንግ)**

Used to document purchases from informal suppliers (e.g., small quarries or local truck drivers) while retaining the 3% WHT rate under MoR Directive 2/2018.10

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Purchase Voucher (Directive 2/2018) / የውስጥ መግዣ ሰነድ (ሞዴል 19 / 3% ዊዝሆልዲንግ) 10 |
| **Exact Trigger Event** | System registration of an inbound material load from an unregistered supplier, utilizing the MoR Directive 2/2018 concession.10 |
| **Complete Mandatory Fields** | purchase\_voucher\_uuid (UUID), voucher\_serial\_no (VARCHAR), supplier\_name (VARCHAR), supplier\_national\_id (VARCHAR), supplier\_phone (VARCHAR), material\_description (ENUM: Meti-Red-Ash, Local-Pumice) 1, volume\_m3 (DECIMAL), measured\_weight\_kg (DECIMAL), unit\_price\_etb (DECIMAL), total\_amount\_etb (DECIMAL), wht\_rate\_pct (DECIMAL; constant 3.0%) 10, withheld\_amount\_etb (DECIMAL; 3% of total) 10, net\_cash\_paid\_etb (DECIMAL), supplier\_ytd\_cumulative\_etb (DECIMAL; auto-blocked if ![][image3] 2,000,000 ETB ceiling).10 |
| **Approval Workflow** | Procurement Officer (Originator) ![][image2] Internal Auditor (Verifier) ![][image2] CFO (Approver). |
| **Accounting/Inventory Impact** | Debit: Raw Material Inventory Account (GL-1102); Credit: Petty Cash Fund / Cash-in-Vault (GL-1101/GL-1112) \[for net paid\]; Credit: Withholding Tax Payable \- 3% (GL-2111).10 |

### **8\. Water Truck Delivery & Volumetric Slip (የውሃ ቦውዘር ማቅረቢያ ሰነድ)**

This document tracks bulk water inputs used for concrete hydration and curing yard systems.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Water Truck Delivery & Volumetric Slip / የውሃ ቦውዘር ማቅረቢያ ሰነድ |
| **Exact Trigger Event** | Inbound water truck exits the yard after discharging water into the plant's curing reservoir, verified by flow meter readings. |
| **Complete Mandatory Fields** | water\_slip\_id (UUID), water\_supplier\_name (VARCHAR), water\_supplier\_tin (VARCHAR), truck\_plate\_no (VARCHAR), flow\_meter\_start (DECIMAL; Liters), flow\_meter\_end (DECIMAL; Liters), net\_volume\_liters (DECIMAL), delivery\_datetime (DATETIME), plant\_utility\_operator\_id (INT). |
| **Approval Workflow** | Plant Utility Operator (Originator) ![][image2] Yard Supervisor (Verifier) ![][image2] Plant Accountant (Approver). |
| **Accounting/Inventory Impact** | Debit: Manufacturing Overhead \- Water Expense Account (GL-5120); Credit: Accounts Payable \- Water Vendor. Physical water balance in the Curing Tank increases in the ERP. |

## **Module 2: Production Batching, Recipe Control, and Curing Cycle**

Concrete hydration and physical curing are time-critical chemical processes. Under Compulsory Ethiopian Standard CES 24, blocks must meet distinct compressive strength targets based on their class (Class A, B, or C).13  
Manufacturing HCBs involves continuous tracking of raw materials as they move through batching, mixing, molding (into various dimensions such as 10 cm, 15 cm, or 20 cm widths), wet-state curing, and final stacking.  
The manufacturing process must handle moisture variations in sand and scoria to maintain the desired water-to-cement ratio:  
![][image4]  
This ratio must be held within the target range of 0.49 to 0.55 to achieve the required structural integrity.1  
The transition of materials from the store to the factory floor is controlled via the Model 20 Store Requisition 9 and Model 22 Store Issue Voucher.9  
The daily optimization of the batch mix, incorporating red ash/scoria and pumice blends (for instance, the optimal 30% red ash replacement ratio) 1, requires real-time formula adjustments.

### **9\. Material Requisition Slip (Model 20\) (የዕቃ መጠየቂያ ሰነድ \- ሞዴል 20\)**

This document records the request from the production department to the warehouse for the release of raw materials.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Material Requisition Slip (Model 20\) / የዕቃ መጠየቂያ ሰነድ (ሞዴል 20\) 9 |
| **Exact Trigger Event** | Scheduling of a daily production run in the ERP Manufacturing Execution System (MES), generating an automated demand for ingredients. |
| **Complete Mandatory Fields** | model\_20\_serial (VARCHAR; system-generated pre-printed series), requester\_cost\_center (VARCHAR), production\_order\_ref (UUID), item\_code (VARCHAR), item\_description (VARCHAR), requested\_quantity\_kg (DECIMAL), material\_location\_id (VARCHAR), requester\_supervisor\_id (INT).9 |
| **Approval Workflow** | Production Shift Supervisor (Originator) ![][image2] Stores Head (Verifier) ![][image2] Plant Manager (Approver).9 |
| **Accounting/Inventory Impact** | Non-financial. The requested inventory quantities are marked as Reserved in the storage locations, preventing reallocation in the stock card (Model 70C).9 |

### **10\. Store Issue Voucher (Model 22\) (የዕቃ ወጪ ማድረጊያ ሰነድ \- ሞዴል 22\)**

The Model 22 confirms the physical transfer of materials from storage to the production floor.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Store Issue Voucher (Model 22\) / የዕቃ ወጪ ማድረጊያ ሰነድ (ሞዴል 22\) 9 |
| **Exact Trigger Event** | Physical loading and dispatch of reserved raw materials from warehouses/silos to the pan mixers, verified by the storekeeper. |
| **Complete Mandatory Fields** | model\_22\_serial (VARCHAR), associated\_model\_20\_ref (VARCHAR) 9, recipient\_cost\_center (VARCHAR), item\_code (VARCHAR), dispatched\_quantity\_kg (DECIMAL), unit\_cost\_etb (DECIMAL), total\_value\_etb (DECIMAL), issuing\_storekeeper\_id (INT), receiving\_operator\_id (INT).9 |
| **Approval Workflow** | Dispatching Storekeeper (Originator) ![][image2] Warehouse Supervisor (Verifier) ![][image2] Materials Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Work-In-Progress (WIP) Inventory Account (GL-1103); Credit: Raw Materials Inventory Asset Account (GL-1102). Stock balance decreases in Model 70C.9 |

### **11\. Daily Batch/Mix Optimization Sheet (የዕለታዊ ድብልቅ ማመጣጠኛ ቅፅ)**

This worksheet calculates recipe adjustments based on daily raw material moisture tests, ensuring water-cement ratios remain within standard tolerances.1

Raw Batch Calculations:  
For aggregate weight adjustment under moist conditions:  
Ma \= Mwet \* (1 \+ w\_moisture)

For scoria blending optimization:  
W\_blend \= R\_scoria \* W\_total \+ (1 \- R\_scoria) \* W\_pumice

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Daily Batch/Mix Optimization Sheet / የዕለታዊ ድብልቅ ማመጣጠኛ ቅፅ |
| **Exact Trigger Event** | Laboratory testing of aggregate moisture levels at the beginning of each shift, requiring recipe updates. |
| **Complete Mandatory Fields** | optimization\_sheet\_id (UUID), date (DATE), shift (ENUM: Day, Night), target\_block\_class (ENUM: Class-A, Class-B, Class-C) 13, mix\_proportion\_ratio (ENUM: 1:6, 1:8) 1, sand\_moisture\_pct (DECIMAL), red\_ash\_moisture\_pct (DECIMAL), target\_water\_cement\_ratio (DECIMAL; range: 0.49 \- 0.55) 1, base\_water\_addition\_liters (DECIMAL), adjusted\_cement\_weight\_kg (DECIMAL), adjusted\_aggregates\_weight\_kg (DECIMAL), corrected\_water\_target\_liters (DECIMAL), operator\_id (INT). |
| **Approval Workflow** | Batching Plant Operator (Originator) ![][image2] QC Supervisor (Verifier) ![][image2] Production Manager (Approver). |
| **Accounting/Inventory Impact** | Non-financial. This sheet updates the active recipe parameters in the batching computer's PLC (Programmable Logic Controller) database. |

### **12\. Bill of Materials (BOM) Backflush Voucher (በጥሬ ዕቃ አጠቃቀም መሠረት ወጪ ማድረጊያ ሰነድ)**

This voucher reconciles physical raw material consumption against theoretical values based on the production count at the end of each shift.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Bill of Materials (BOM) Backflush Voucher / በጥሬ ዕቃ አጠቃቀም መሠረት ወጪ ማድረጊያ ሰነድ |
| **Exact Trigger Event** | Daily close of the production run in the ERP Manufacturing module, comparing actual raw material issues (Model 22\) against standard recipe consumption.9 |
| **Complete Mandatory Fields** | backflush\_id (UUID), production\_order\_ref (UUID), product\_sku (VARCHAR; e.g., HCB-15-ClassB), total\_output\_units (INT), theoretical\_material\_qty\_kg (DECIMAL), actual\_material\_qty\_kg (DECIMAL), material\_variance\_kg (DECIMAL), cost\_accountant\_id (INT). |
| **Approval Workflow** | Production Shift Supervisor (Originator) ![][image2] Cost Accountant (Verifier) ![][image2] Production Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Manufacturing Material Variance Account (GL-5105); Credit: WIP Inventory Account (GL-1103). Resolves variances between theoretical BOM and physical issues. |

### **13\. Wet Yard Stacking Slip (እርጥብ ብሎክ መደርደሪያ ሰነድ)**

This document tracks wet blocks as they are transferred from the molding machines to the wet yard for initial hydration.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Wet Yard Stacking Slip / እርጥብ ብሎክ መደርደሪያ ሰነድ |
| **Exact Trigger Event** | Forklift driver transfers wet molded blocks from machine line to wet yard lanes. |
| **Complete Mandatory Fields** | wet\_stacking\_slip\_id (UUID), production\_order\_ref (UUID), machine\_line\_id (VARCHAR), wet\_yard\_lane\_grid (VARCHAR), block\_class (ENUM: Class-A, Class-B, Class-C) 13, dimensions\_mm (VARCHAR; e.g., 400x200x200) 13, quantity\_molded (INT), stacker\_team\_id (VARCHAR). |
| **Approval Workflow** | Machine Line Lead (Originator) ![][image2] Wet Yard Supervisor (Verifier) ![][image2] Production Manager (Approver). |
| **Accounting/Inventory Impact** | Shifts physical inventory location state from Molding Line to Wet Curing Yard in ERP. |

### **14\. Daily Water-Sprinkling/Curing Progress Log (የውሃ ማርከስና ህክምና ክትትል ሰነድ)**

This log records the active water-curing cycle required to ensure proper hydration and structural strength.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Daily Water-Sprinkling/Curing Progress Log / የውሃ ማርከስና ህክምና ክትትል ሰነድ |
| **Exact Trigger Event** | Curing yard personnel complete a scheduled watering run across active lanes. |
| **Complete Mandatory Fields** | curing\_log\_id (UUID), curing\_lane\_grid (VARCHAR), block\_batch\_lot\_no (VARCHAR), curing\_day\_count (INT; range: 1 \- 14), water\_volume\_sprinkled\_liters (DECIMAL), sprinkling\_time\_stamp (DATETIME), sprinkling\_operator\_id (INT). |
| **Approval Workflow** | Curing Yard Operator (Originator) ![][image2] Yard Shift Lead (Verifier) ![][image2] Quality Assurance Lead (Approver). |
| **Accounting/Inventory Impact** | Non-financial. Updates the aging parameter of the batch in ERP, allowing progression to next lifecycle stage. |

### **15\. QA Compressive Strength Lab Crushing Voucher \- 7 Day Test (የ7 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት)**

This document records the results of early strength tests to monitor structural development during curing.1

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | QA Compressive Strength Lab Crushing Voucher \- 7 Day Test / የ7 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት 1 |
| **Exact Trigger Event** | Testing lab operator crushes 3 sample blocks from a batch that has cured for 7 days to evaluate early strength.1 |
| **Complete Mandatory Fields** | crushing\_voucher\_7d\_id (UUID), batch\_lot\_no (VARCHAR), sample\_age\_days (INT; constant 7), length\_mm (DECIMAL) 13, width\_mm (DECIMAL) 13, gross\_area\_mm2 (DECIMAL), crushing\_load\_kn (DECIMAL) 13, calculated\_strength\_mpa (DECIMAL; formula: Load/Area) 13, target\_strength\_60pct\_class\_mpa (DECIMAL), pass\_fail\_status (BOOLEAN), testing\_technician\_id (INT). |
| **Approval Workflow** | Lab Testing Technician (Originator) ![][image2] Quality Assurance Lead (Verifier) ![][image2] Production Director (Approver). |
| **Accounting/Inventory Impact** | Non-financial. ERP updates batch quality status to 7-Day Approved in the system database. |

### **16\. QA Compressive Strength Lab Crushing Voucher \- 14 Day Test (የ14 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት)**

This document records strength development tests at the 14-day curing milestone.1

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | QA Compressive Strength Lab Crushing Voucher \- 14 Day Test / የ14 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት 1 |
| **Exact Trigger Event** | Testing lab operator crushes 3 sample blocks from a batch that has cured for 14 days to evaluate strength development.1 |
| **Complete Mandatory Fields** | crushing\_voucher\_14d\_id (UUID), batch\_lot\_no (VARCHAR), sample\_age\_days (INT; constant 14), length\_mm (DECIMAL) 13, width\_mm (DECIMAL) 13, gross\_area\_mm2 (DECIMAL), crushing\_load\_kn (DECIMAL) 13, calculated\_strength\_mpa (DECIMAL) 13, pass\_fail\_status (BOOLEAN), testing\_technician\_id (INT). |
| **Approval Workflow** | Lab Testing Technician (Originator) ![][image2] Quality Assurance Lead (Verifier) ![][image2] Production Director (Approver). |
| **Accounting/Inventory Impact** | Non-financial. ERP updates batch quality status to 14-Day Approved in the system database. |

### **17\. QA Compressive Strength Lab Crushing Voucher \- 28 Day Test (የ28 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት)**

This document records the results of the final 28-day crushing tests to verify compliance with Compulsory Ethiopian Standard CES 24 before sale.13

Compressive Strength Calculation:  
\\sigma \= \\frac{P\_{max} \\cdot 10^3}{A\_{gross}}

Where:  
\\sigma \= Compressive strength in Megapascals (MPa)   
P\_{max} \= Maximum failure load in Kilonewtons (kN)   
A\_{gross} \= Gross cross-sectional area in square millimeters (mm^2) 

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | QA Compressive Strength Lab Crushing Voucher \- 28 Day Test / የ28 ቀን የብሎኬት ጥንካሬ መፈተኛ ምስክር ወረቀት 13 |
| **Exact Trigger Event** | Testing lab operator crushes 6 sample blocks from a batch that has cured for 28 days to verify compliance with CES 24\.13 |
| **Complete Mandatory Fields** | crushing\_voucher\_28d\_id (UUID), batch\_lot\_no (VARCHAR), sample\_age\_days (INT; constant 28), length\_mm (DECIMAL) 13, width\_mm (DECIMAL) 13, gross\_area\_mm2 (DECIMAL), crushing\_load\_kn (DECIMAL) 13, average\_strength\_6\_units\_mpa (DECIMAL; Class A ![][image3] 4.2, Class B ![][image3] 4.0, Class C ![][image3] 2.0) 13, individual\_unit\_strength\_mpa (DECIMAL; Class A ![][image3] 3.8, Class B ![][image3] 3.2, Class C ![][image3] 1.8) 13, calibration\_expiry\_date (DATE; compression press verification), testing\_technician\_id (INT). |
| **Approval Workflow** | Lab Testing Technician (Originator) ![][image2] Quality Assurance Lead (Verifier) ![][image2] Plant Director (Approver). |
| **Accounting/Inventory Impact** | Non-financial. Unlocks the batch for final inventory transfer. Status changes from Curing WIP to Approved Finished Goods in the ERP. |

### **18\. Finished Goods Transfer Note (ያለቀለት ምርት ማዛወሪያ ሰነድ)**

This document records the transfer of approved blocks from the curing lanes to the main finished goods yard, ready for commercial sale.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Finished Goods Transfer Note / ያለቀለት ምርት ማዛወሪያ ሰነድ |
| **Exact Trigger Event** | Quality team approves the 28-day strength test, authorizing the transfer of blocks to the sales yard.1 |
| **Complete Mandatory Fields** | fg\_transfer\_id (UUID), associated\_qa\_voucher\_ref (UUID) 13, batch\_lot\_no (VARCHAR), product\_sku (VARCHAR; e.g., HCB-20-ClassB), total\_block\_count (INT), source\_location\_id (VARCHAR; Curing Yard), destination\_location\_id (VARCHAR; Finished Goods Yard Grid), forklift\_driver\_id (INT), receiving\_storekeeper\_id (INT). |
| **Approval Workflow** | Stacking Yard Supervisor (Originator) ![][image2] Finished Goods Storekeeper (Verifier) ![][image2] Production Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Finished Goods Inventory Account (GL-1104); Credit: WIP Inventory Account (GL-1103). Physical inventory balances update in the database. |

## **Module 3: Logistics, Commercial Sales, and Fiscal Tax Compliance**

In the Ethiopian tax jurisdiction, commercial transactions are subject to strict compliance oversight. Under Ministry of Revenues Directive 188/2024 (as amended by Directive 1099/2025), all manual sales receipts and invoices must feature a unique, government-generated identification QR code.5 This QR code, measuring at least 2 cm x 2 cm, must be printed in the top-right header using penetrating ink on security paper printed by authorized state-run enterprises, such as Berhanena Selam.5  
Receipts issued without this unique code are invalid, resulting in the rejection of VAT deductions and business expense claims.7  
Furthermore, cash transactions must be closely managed. Large commercial sales are typically settled via Cash Payment Orders (CPOs), direct bank transfers (such as through the Commercial Bank of Ethiopia or Dashen Bank), or mobile payment systems like Telebirr and CBE Birr.  
To transport finished blocks beyond the boundaries of Addis Ababa, vehicles must carry official documentation, including a Delivery Challan, a VAT invoice, and an Outbound Gate Pass (ይለፍ) to clear regional police and tax checkpoints.3

### **19\. Sales Quotation (የዋጋ ማቅረቢያ ሰነድ)**

The initial document sent to potential buyers detailing the pricing, specifications, and availability of the blocks.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Sales Quotation / የዋጋ ማቅረቢያ ሰነድ |
| **Exact Trigger Event** | Sales team receives a request for proposals from a developer, generating a price quote in the ERP. |
| **Complete Mandatory Fields** | quotation\_id (UUID), date (DATE), customer\_name (VARCHAR), customer\_tin (VARCHAR), customer\_address (VARCHAR), item\_sku (VARCHAR), unit\_price\_ex\_works\_etb (DECIMAL), offered\_quantity (INT), subtotal\_etb (DECIMAL), estimated\_vat\_etb (DECIMAL; 15%), total\_gross\_etb (DECIMAL), validity\_period\_days (INT), sales\_exec\_id (INT). |
| **Approval Workflow** | Sales Executive (Originator) ![][image2] Commercial Lead (Verifier) ![][image2] Commercial Director (Approver). |
| **Accounting/Inventory Impact** | Non-financial. Quotation is logged in the CRM database with an Active status. |

### **20\. Proforma Invoice (ፕሮፎርማ ደረሰኝ)**

A binding document issued to the customer to facilitate pre-payment, bank loan approvals, or the generation of a bank Cash Payment Order (CPO).

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Proforma Invoice / ፕሮፎርማ ደረሰኝ |
| **Exact Trigger Event** | Customer accepts a sales quote and requests a formal payment reference to arrange billing. |
| **Complete Mandatory Fields** | proforma\_id (UUID), date (DATE), customer\_name (VARCHAR), customer\_tin (VARCHAR), item\_sku (VARCHAR), unit\_prices\_etb (DECIMAL), total\_net\_etb (DECIMAL), vat\_15\_pct (DECIMAL; 15%), total\_gross\_etb (DECIMAL), payment\_terms (ENUM: CPO, Bank-Transfer, Telebirr, CBE-Birr), delivery\_terms (ENUM: Ex-Works, Delivered), commercial\_sig (BLOB). |
| **Approval Workflow** | Sales Executive (Originator) ![][image2] Sales Supervisor (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Non-financial. System allocates target stock as Committed to Order in the yard database. |

### **21\. Cash Receipt Voucher (CRV) (የጥሬ ገንዘብ መቀበያ ሰነድ)**

The official document confirming the receipt of funds, whether cash, CPO, bank transfer, or mobile payment.19

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Cash Receipt Voucher (CRV) / የጥሬ ገንዘብ መቀበያ ሰነድ 19 |
| **Exact Trigger Event** | Finance team verifies reception of a bank transfer, CPO, or cash payment.19 |
| **Complete Mandatory Fields** | crv\_id (VARCHAR; system-generated pre-printed series) 19, date\_of\_payment (DATE) 19, customer\_name (VARCHAR) 19, customer\_tin (VARCHAR), payment\_mode (ENUM: CPO, Bank-Transfer, Cash, Telebirr), bank\_transaction\_reference (VARCHAR; e.g., CBE Tx ID) 19, associated\_proforma\_ref (UUID), amount\_received\_etb (DECIMAL) 19, cashier\_operator\_id (INT).19 |
| **Approval Workflow** | Plant Cashier (Originator) ![][image2] Treasury Supervisor (Verifier) ![][image2] Finance Manager (Approver).19 |
| **Accounting/Inventory Impact** | Debit: Main Bank Account (e.g., CBE Cash Account GL-1111); Credit: Customer Advances Liability Account (GL-2104).19 |

### **22\. Official MoR Fiscal VAT Invoice (ህጋዊ የሽያጭ ደረሰኝ ከQR ኮድ ጋር)**

The legally mandated tax invoice required to record the sale, which must comply with all modern Ministry of Revenues printing and data standards.5

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Official MoR Fiscal VAT Invoice / ህጋዊ የሽያጭ ደረሰኝ (ከQR ኮድ ጋር) 5 |
| **Exact Trigger Event** | System approves the Cash Receipt Voucher (CRV), authorizing the final billing of the order.19 |
| **Complete Mandatory Fields** | invoice\_serial\_no (VARCHAR; MoR pre-printed range) 12, efd\_registration\_code (VARCHAR; device code) 12, mor\_unique\_qr\_code (BLOB; 2 cm x 2 cm top-right header verified via MoR portal API) 5, seller\_tin (VARCHAR; company TIN) 12, seller\_vat\_no (VARCHAR) 12, seller\_branch\_address (VARCHAR) 6, buyer\_tin (VARCHAR) 12, buyer\_vat\_no (VARCHAR), item\_sku (VARCHAR) 12, quantity (INT) 12, unit\_price (DECIMAL) 12, taxable\_total\_etb (DECIMAL) 12, vat\_15\_amount\_etb (DECIMAL) 12, grand\_total\_etb (DECIMAL) 12, issue\_datetime (DATETIME).12 |
| **Approval Workflow** | Billing Officer (Originator) ![][image2] Senior Tax Accountant (Verifier) ![][image2] CFO (Approver). |
| **Accounting/Inventory Impact** | Debit: Customer Advances Liability Account (GL-2104); Credit: Sales Revenue (GL-4101); Credit: VAT Output Payable (GL-2108).12 |

### **23\. Credit Note (ክሬዲት ኖት)**

Used to record adjustments for returned goods or billing corrections, ensuring compliant tax adjustments.12

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Credit Note / ክሬዲት ኖት 12 |
| **Exact Trigger Event** | Quality team confirms the return of damaged blocks, or finance approves an invoice price correction.12 |
| **Complete Mandatory Fields** | credit\_note\_serial (VARCHAR), original\_fiscal\_invoice\_ref (VARCHAR) 12, customer\_name (VARCHAR) 12, customer\_tin (VARCHAR), credit\_reason\_code (ENUM: Damage-on-Delivery, Over-billing, Volumetric-Shortage), returned\_qty (INT), unit\_price\_credit\_etb (DECIMAL), base\_credit\_amount\_etb (DECIMAL), vat\_15\_credit\_etb (DECIMAL), total\_credit\_value\_etb (DECIMAL) 12, qa\_inspector\_id (INT).12 |
| **Approval Workflow** | Customer Relations Representative (Originator) ![][image2] Chief Accountant (Verifier) ![][image2] CFO (Approver). |
| **Accounting/Inventory Impact** | Debit: Sales Returns & Allowances (GL-4102), Debit: VAT Output Payable (GL-2108); Credit: Accounts Receivable / Customer Advance Liability (GL-2104). Stock returns to yard quarantine. |

### **24\. Debit Note (ዴቢት ኖት)**

Used to record adjustments for billing undercharges or price updates.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Debit Note / ዴቢት ኖት |
| **Exact Trigger Event** | Finance identifies an undercharge or billing error on a issued invoice, requiring a corrective billing adjustment. |
| **Complete Mandatory Fields** | debit\_note\_serial (VARCHAR), original\_fiscal\_invoice\_ref (VARCHAR), customer\_name (VARCHAR), customer\_tin (VARCHAR), debit\_reason (VARCHAR), adjustment\_base\_amount\_etb (DECIMAL), additional\_vat\_15\_etb (DECIMAL), total\_debit\_value\_etb (DECIMAL), auditor\_id (INT). |
| **Approval Workflow** | Sales Auditor (Originator) ![][image2] Chief Accountant (Verifier) ![][image2] Finance Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Accounts Receivable (GL-1105); Credit: Sales Revenue (GL-4101); Credit: VAT Output Payable (GL-2108). |

### **25\. Delivery Challan (Model 21 Delivery Order) (የዕቃ መላኪያ ትዕዛዝ \- ሞዴል 21\)**

This document authorizes the warehouse to release and load finished blocks onto vehicles for transport.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Delivery Challan (Model 21 Delivery Order) / የዕቃ መላኪያ ትዕዛዝ (ሞዴል 21\) 9 |
| **Exact Trigger Event** | Posting of the official MoR Fiscal VAT Invoice, prompting the system to generate a warehouse loading order.5 |
| **Complete Mandatory Fields** | model\_21\_serial (VARCHAR), associated\_fiscal\_invoice\_ref (VARCHAR), customer\_name (VARCHAR), delivery\_site\_address (VARCHAR), item\_sku (VARCHAR), quantity\_dispatched (INT), carrier\_truck\_plate\_no (VARCHAR), driver\_name (VARCHAR), forklift\_loader\_id (INT), dispatch\_storekeeper\_id (INT).9 |
| **Approval Workflow** | Logistics Coordinator (Originator) ![][image2] FG Storekeeper (Verifier) ![][image2] Commercial Director (Approver).9 |
| **Accounting/Inventory Impact** | Debit: Cost of Goods Sold (COGS) Account (GL-5101); Credit: Finished Goods Inventory Account (GL-1104). Updates stock balance cards (Model 70C).9 |

### **26\. Outbound Gate Pass (የዕቃ መውጫ ይለፍ)**

The final security and compliance clearance document required for vehicles to exit the yard and travel through transport checkpoints.3

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Outbound Gate Pass / የዕቃ መውጫ ይለፍ 3 |
| **Exact Trigger Event** | Loaded delivery truck arrives at the yard gate, where security matches the physical load with the Delivery Challan.9 |
| **Complete Mandatory Fields** | gate\_pass\_id (UUID), gate\_pass\_serial (VARCHAR), dispatch\_datetime (DATETIME), associated\_model\_21\_ref (VARCHAR) 9, associated\_fiscal\_invoice\_ref (VARCHAR), driver\_name (VARCHAR), driver\_license\_no (VARCHAR), truck\_plate\_no (VARCHAR), verified\_loaded\_block\_count (INT), gate\_security\_officer\_id (INT). |
| **Approval Workflow** | Gate Security Officer (Originator) ![][image2] Security Supervisor (Verifier) ![][image2] Logistics Director (Approver). |
| **Accounting/Inventory Impact** | Non-financial. Releases physical inventory from yard custody, changing order status to Dispatched in the ERP. |

## **Module 4: Inventory Control and Waste Management**

Hollow concrete block production is subject to physical loss and breakage. Damage can occur during various stages: green-state molding, curing, yard stacking, and vehicle loading.  
For cost accounting and forensic audit purposes, every loss must be categorized and recorded to prevent raw material loss from being used to hide unrecorded sales.  
Physical inventory counts must be performed regularly, and any differences between the physical stock and the ERP inventory ledger (such as Model 70C) must be formally reconciled.9

### **27\. Green-State (Wet) Re-crush Voucher (ጥሬ (እርጥብ) ብሎኬት መልሶ መፍጫ ሰነድ)**

This document records the recovery of material from newly molded wet blocks that fail inspection and are recycled back into the pan mixers before hydration.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Green-State (Wet) Re-crush Voucher / ጥሬ (እርጥብ) ብሎኬት መልሶ መፍጫ ሰነድ |
| **Exact Trigger Event** | Quality inspection identifies defects on wet blocks at the extrusion line, rejecting them before curing. |
| **Complete Mandatory Fields** | re\_crush\_voucher\_id (UUID), date (DATE), shift (ENUM: Day, Night), machine\_line\_id (VARCHAR), quantity\_damaged\_units (INT), estimated\_wet\_material\_mass\_kg (DECIMAL), reclaimed\_cement\_estimate\_kg (DECIMAL), reclaimed\_aggregate\_estimate\_kg (DECIMAL), pan\_mixer\_destination\_id (VARCHAR), molding\_operator\_id (INT). |
| **Approval Workflow** | Molding Line Lead (Originator) ![][image2] Shift Supervisor (Verifier) ![][image2] Production Manager (Approver). |
| **Accounting/Inventory Impact** | Non-financial. Material remains within the WIP inventory loop; records scrap variance on the production line in the ERP. |

### **28\. Curing-Stage Breakage Log (በህክምና ሂደት የሰበሩ ብሎኬቶች መመዝገቢያ ሰነድ)**

This log tracks blocks that break during water curing, handling, or stacking within the curing yard.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Curing-Stage Breakage Log / በህክምና ሂደት የሰበሩ ብሎኬቶች መመዝገቢያ ሰነድ |
| **Exact Trigger Event** | Discovery and removal of cracked or broken blocks from the curing lanes during daily watering or inspection. |
| **Complete Mandatory Fields** | curing\_breakage\_log\_id (UUID), date (DATE), batch\_lot\_no (VARCHAR), curing\_lane\_grid (VARCHAR), quantity\_broken (INT), standard\_material\_cost\_per\_unit\_etb (DECIMAL), total\_valuation\_loss\_etb (DECIMAL), scrap\_coordinator\_id (INT). |
| **Approval Workflow** | Curing Inspector (Originator) ![][image2] Yard Supervisor (Verifier) ![][image2] Cost Accountant (Approver). |
| **Accounting/Inventory Impact** | Debit: Work-In-Progress Scrap Expense Account (GL-5106); Credit: WIP Production Account (GL-1103). Removes lost units from active production runs. |

### **29\. Yard Stacking Damage Slip (በምርት ክምችት ላይ የደረሰ ጉዳት መመዝገቢያ ሰነድ)**

This document records damage to finished, cured blocks while they are stored in the main stacking yard.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Yard Stacking Damage Slip / በምርት ክምችት ላይ የደረሰ ጉዳት መመዝገቢያ ሰነድ |
| **Exact Trigger Event** | Warehouse team identifies damage to cured blocks during storage or stack movements. |
| **Complete Mandatory Fields** | stacking\_damage\_slip\_id (UUID), yard\_grid\_location (VARCHAR), product\_sku (VARCHAR), quantity\_damaged\_units (INT), weighted\_average\_cost\_per\_unit\_etb (DECIMAL), total\_valuation\_loss\_etb (DECIMAL), damage\_reason\_code (ENUM: Collapse, Handling-Impact, Weathering), stacking\_supervisor\_id (INT). |
| **Approval Workflow** | Yard Stock Clerk (Originator) ![][image2] Warehouse Supervisor (Verifier) ![][image2] Materials Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Inventory Obsolescence & Stacking Loss Account (GL-5107); Credit: Finished Goods Inventory Asset Account (GL-1104). |

### **30\. Loading/Forklift Scrap Note (ጫኝ/ፎርክሊፍት አደጋ ምርት ብክነት ሰነድ)**

Records breakage that occurs during the loading of delivery trucks, which must be documented to explain variances between the billed and delivered quantities.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Loading and Forklift Scrap Note / ጫኝ/ፎርክሊፍት አደጋ ምርት ብክነት ሰነድ |
| **Exact Trigger Event** | Forklift operator drops or damages finished blocks during loading onto delivery trucks. |
| **Complete Mandatory Fields** | loading\_scrap\_note\_id (UUID), associated\_model\_21\_ref (VARCHAR) 9, forklift\_operator\_id (INT), loading\_bay\_no (VARCHAR), quantity\_damaged (INT), total\_valuation\_loss\_etb (DECIMAL), replacement\_issued (BOOLEAN), dispatch\_supervisor\_id (INT). |
| **Approval Workflow** | Forklift Driver (Originator) ![][image2] Loading Supervisor (Verifier) ![][image2] Plant Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: Outbound Logistics Loading Scrap Account (GL-5108); Credit: Finished Goods Inventory Asset Account (GL-1104). |

### **31\. Physical Stock Count Variance Adjustment Voucher (የቆጠራ ልዩነት ማስተካከያ ሰነድ)**

The official document used to adjust the ERP inventory balances (such as Model 70C) to match the physical stock counts.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Physical Stock Count Variance Adjustment Voucher / የቆጠራ ልዩነት ማስተካከያ ሰነድ 9 |
| **Exact Trigger Event** | Inventory audits identify differences between physical yard counts and ERP ledger balances.20 |
| **Complete Mandatory Fields** | stock\_adjustment\_voucher\_id (UUID), associated\_count\_sheet\_ref (VARCHAR), count\_date (DATE), warehouse\_yard\_grid (VARCHAR), item\_code (VARCHAR), erp\_ledger\_qty (DECIMAL), physical\_counted\_qty (DECIMAL), variance\_qty (DECIMAL), unit\_cost\_etb (DECIMAL), total\_adjustment\_valuation\_etb (DECIMAL), adjustment\_type (ENUM: Write-Off, Write-In), auditor\_id (INT). |
| **Approval Workflow** | Inventory Controller (Originator) ![][image2] Internal Auditor (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Positive Variance: Debit: Finished Goods Inventory Account (GL-1104); Credit: Stock Gain Account (GL-4105). Negative Variance: Debit: Stock Loss Account (GL-5109); Credit: Finished Goods Inventory Account (GL-1104).21 |

## **Module 5: Treasury, Expense, and Plant Accounting**

Managing financial resources in an industrial environment requires control over petty cash and formal accounting procedures.  
Petty cash must be managed through structured vouchers 19 to cover immediate costs like machinery lubricants, site cleaning supplies, and driver meal allowances.  
All cash receipts must be deposited into the company's verified bank accounts, and monthly journal entries must be recorded to account for the depreciation of high-value manufacturing equipment, such as pan mixers, molding machines, and logistics fleets.

### **32\. Petty Cash Voucher (PCV) (የቸርቻሪ ወጪ ሰነድ)**

This voucher documents small cash disbursements from the office safe for minor, immediate plant operations.19

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Petty Cash Voucher (PCV) / የቸርቻሪ ወጪ ሰነድ 19 |
| **Exact Trigger Event** | Cashier receives an approved request for minor cash purchases, issuing funds from the petty cash safe.19 |
| **Complete Mandatory Fields** | pcv\_serial\_no (VARCHAR; pre-printed system sequence) 19, transaction\_date (DATE) 19, payee\_name (VARCHAR) 19, expense\_category (ENUM: Machine-Grease, Driver-Allowance, Site-Cleaning-Supplies, Consumables), item\_description (VARCHAR) 19, disbursed\_amount\_etb (DECIMAL) 19, gl\_account\_code (VARCHAR) 19, petty\_cash\_custodian\_id (INT).19 |
| **Approval Workflow** | Petty Cash Custodian (Originator) ![][image2] Plant Accountant (Verifier) ![][image2] Finance Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: Operational Expense Account (e.g., Plant Consumables GL-5210); Credit: Petty Cash Fund Account (GL-1101).19 |

### **33\. Petty Cash Replenishment Journal (የቸርቻሪ ወጪ ማጠቃለያ ሰነድ)**

This document summarizes all petty cash spending to authorize the replenishment of the fund back to its float level.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Petty Cash Replenishment Journal / የቸርቻሪ ወጪ ማጠቃለያ ሰነድ |
| **Exact Trigger Event** | Petty cash fund balances fall below the minimum threshold, requiring a replenishment transfer. |
| **Complete Mandatory Fields** | replenishment\_id (UUID), reporting\_period\_start (DATE), reporting\_period\_end (DATE), fund\_float\_limit\_etb (DECIMAL), sum\_disbursed\_vouchers\_etb (DECIMAL), cash\_remaining\_in\_safe\_etb (DECIMAL), replenishment\_requested\_amount\_etb (DECIMAL), attached\_pcv\_range (VARCHAR), cashier\_id (INT). |
| **Approval Workflow** | Petty Cash Custodian (Originator) ![][image2] Chief Accountant (Verifier) ![][image2] Finance Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Petty Cash Fund Account (GL-1101); Credit: Main Commercial Bank Account (GL-1111) \[reconciles and replenishes cash\]. |

### **34\. Bank Deposit Slip (የባንክ ገቢ ማድረጊያ ሰነድ)**

Documents the deposit of cash or CPOs into the company's commercial bank accounts.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Bank Deposit Slip / የባንክ ገቢ ማድረጊያ ሰነድ |
| **Exact Trigger Event** | Treasury clerk deposits cash or physical customer CPOs at the bank, returning with a stamped slip. |
| **Complete Mandatory Fields** | deposit\_slip\_id (UUID), bank\_name (ENUM: CBE, Dashen, Awash), bank\_account\_no (VARCHAR), account\_name (VARCHAR; company name), cash\_denominations\_breakdown (VARCHAR), cpo\_reference\_numbers (VARCHAR), total\_deposited\_value\_etb (DECIMAL), bank\_teller\_stamp\_date (DATETIME), depositing\_clerk\_id (INT). |
| **Approval Workflow** | Treasury Assistant (Originator) ![][image2] Head Treasurer (Verifier) ![][image2] CFO (Approver). |
| **Accounting/Inventory Impact** | Debit: Main Commercial Bank Account (GL-1111); Credit: Cash-on-Hand/Undeposited Funds (GL-1112). Reconciles physical cash balances. |

### **35\. Journal Voucher (JV) (የሂሳብ ማስተካከያ ሰነድ)**

Used to record non-cash financial transactions, including corrections, accruals, and monthly closing adjustments.19

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Journal Voucher / የሂሳብ ማስተካከያ ሰነድ 19 |
| **Exact Trigger Event** | Finance team processes periodic adjustments, corrections, or tax allocations in the general ledger.19 |
| **Complete Mandatory Fields** | journal\_voucher\_id (VARCHAR; system-generated series) 19, posting\_date (DATE) 19, debit\_gl\_account (VARCHAR), credit\_gl\_account (VARCHAR) 19, cost\_center (VARCHAR), debit\_amount\_etb (DECIMAL) 19, credit\_amount\_etb (DECIMAL) 19, narrative\_justification (VARCHAR) 19, preparer\_id (INT), approver\_id (INT). |
| **Approval Workflow** | General Ledger Accountant (Originator) ![][image2] Chief Accountant (Verifier) ![][image2] CFO (Approver). |
| **Accounting/Inventory Impact** | Adjusts designated general ledger accounts, depending on the transaction type. Debit and Credit values must balance. |

### **36\. Fixed Asset Depreciation Voucher (የቋሚ ንብረት ዕርጅና መመዝገቢያ ሰነድ)**

Records the monthly depreciation expense of high-value manufacturing equipment and machinery.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Fixed Asset Depreciation Voucher / የቋሚ ንብረት ዕርጅና መመዝገቢያ ሰነድ |
| **Exact Trigger Event** | Month-end close process in the ERP Fixed Assets module, running depreciation calculations for plant machinery. |
| **Complete Mandatory Fields** | depreciation\_voucher\_id (UUID), asset\_tag\_no (VARCHAR; e.g., molding-machine-01, pan-mixer-02, forklift-03), asset\_class (ENUM: Molding-Machinery, Mixing-Equipment, Logistics-Fleet), historical\_cost\_etb (DECIMAL), estimated\_useful\_life\_months (INT), accumulated\_depreciation\_to\_date\_etb (DECIMAL), monthly\_depreciation\_expense\_etb (DECIMAL), net\_book\_value\_etb (DECIMAL), depreciation\_accountant\_id (INT). |
| **Approval Workflow** | Fixed Assets Accountant (Originator) ![][image2] Chief Accountant (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Debit: Depreciation Expense Account (GL-5301; Manufacturing Overhead); Credit: Accumulated Depreciation Account (GL-1201; Asset Contra Account). |

## **Module 6: HR, Shift Management, and Piece-Rate Labor**

The manufacturing facility relies on labor-intensive yard operations. Many workers, including production operators, stackers, and loaders, are compensated using piece-rate systems based on their daily production or loading volumes.  
This model requires tracking daily attendance, piece-rate productivity metrics, and overtime hours to calculate payroll and ensure compliance with local labor regulations and tax withholding standards.9

### **37\. Daily Shift Attendance Log (የዕለታዊ የስራ ሰዓት መቆጣጠሪያ ሰነድ)**

Records the daily attendance of all factory workers to determine shift presence and basic payroll allocations.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Daily Shift Attendance Log / የዕለታዊ የስራ ሰዓት መቆጣጠሪያ ሰነድ |
| **Exact Trigger Event** | Gate terminal captures biometrics or manual roster updates as workers enter the plant for their shift. |
| **Complete Mandatory Fields** | attendance\_log\_id (UUID), date (DATE), shift\_type (ENUM: Day, Night), department\_id (ENUM: Molding-Line, Stacking-Yard, Loading-Bay), employee\_id (INT), employee\_name (VARCHAR), clock\_in\_time (DATETIME), clock\_out\_time (DATETIME), standard\_hours\_worked (DECIMAL), overtime\_hours\_worked (DECIMAL), attendance\_clerk\_id (INT). |
| **Approval Workflow** | Attendance Clerk (Originator) ![][image2] Shift Supervisor (Verifier) ![][image2] HR Operations Lead (Approver). |
| **Accounting/Inventory Impact** | Non-financial. This data serves as the source information for generating monthly payroll calculations. |

### **38\. Piece-Rate Labor Production Voucher (የቁራጭ ስራ ምርት መመዝገቢያ ሰነድ)**

This voucher tracks individual or team production output to calculate piece-rate compensation.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Piece-Rate Labor Production Voucher / የቁራጭ ስራ ምርት መመዝገቢያ ሰነድ |
| **Exact Trigger Event** | Yard team completes a stacking or loading run, prompting physical output verification. |
| **Complete Mandatory Fields** | piece\_rate\_voucher\_id (UUID), production\_date (DATE), employee\_group\_id (VARCHAR), activity\_type (ENUM: Molding, Stacking, Loading), block\_specification (VARCHAR; size & class), verified\_quantity\_units (INT), pay\_rate\_per\_unit\_etb (DECIMAL), total\_wages\_earned\_etb (DECIMAL), associated\_production\_order\_ref (UUID), yard\_supervisor\_id (INT). |
| **Approval Workflow** | Production Yard Supervisor (Originator) ![][image2] Cost Accountant (Verifier) ![][image2] Payroll Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: Direct Labor Cost (WIP Inventory Account GL-1103); Credit: Accrued Piece-Rate Salaries Payable Account (GL-2122). |

### **39\. Overtime Authorization Slip (የትርፍ ሰዓት ስራ ፈቃድ ሰነድ)**

Documents the approval of overtime hours for employees working beyond standard shift limits to meet high production demands.

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Overtime Authorization Slip / occurrence / የትርፍ ሰዓት ስራ ፈቃድ ሰነድ |
| **Exact Trigger Event** | Production supervisor schedules extended shifts to meet urgent customer orders, prompting a system request. |
| **Complete Mandatory Fields** | overtime\_slip\_id (UUID), overtime\_date (DATE), employee\_id (INT), department (VARCHAR), normal\_hours\_worked (DECIMAL), overtime\_hours\_worked (DECIMAL), rate\_multiplier (DECIMAL; range: 1.25, 1.50, 2.00 as per Labor Law), overtime\_reason\_code (ENUM: Backlog, Fleet-Delay, Machine-Downtime), supervisor\_signature (BLOB). |
| **Approval Workflow** | Shift Supervisor (Originator) ![][image2] HR Operations Lead (Verifier) ![][image2] Plant Manager (Approver). |
| **Accounting/Inventory Impact** | Debit: Overtime Expense Account (GL-5132; Production Overhead); Credit: Accrued Wages Payable Account (GL-2121). |

### **40\. Cash Advance/Salary Voucher Record (የደመወዝ ቅድሚያ ክፍያ መጠየቂያ ሰነድ)**

Used to document salary advances issued to workers, which are later deducted from their monthly payroll payments.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Cash Advance Request Voucher / የደመወዝ ቅድሚያ ክፍያ መጠየቂያ ሰነድ 9 |
| **Exact Trigger Event** | Employee submits an approved request for a salary advance, prompting cash disbursement.9 |
| **Complete Mandatory Fields** | advance\_voucher\_id (UUID), request\_date (DATE), employee\_id (INT), employee\_name (VARCHAR), base\_salary\_etb (DECIMAL), advance\_requested\_amount\_etb (DECIMAL), monthly\_deduction\_rate\_etb (DECIMAL), repayment\_period\_months (INT), payroll\_accountant\_sig (BLOB), recipient\_signature (BLOB).9 |
| **Approval Workflow** | Payroll Clerk (Originator) ![][image2] HR Manager (Verifier) ![][image2] Finance Director (Approver). |
| **Accounting/Inventory Impact** | Debit: Employee Salary Advance Receivable Account (GL-1152); Credit: Cash-in-Vault / Main Bank Account (GL-1112/GL-1111). |

### **41\. Salary Payroll Sheet (የደመወዝ መከፈያ ሰነድ)**

The monthly payroll ledger summarizing basic salaries, piece-rate earnings, allowances, deductions, and tax withholdings.9

| Component | Specification |
| :---- | :---- |
| **System Name & Local Name** | Salary Payroll Sheet / የደመወዝ መከፈያ ሰነድ 9 |
| **Exact Trigger Event** | Month-end close triggers the payroll calculation run in the ERP Human Capital Management (HCM) module. |
| **Complete Mandatory Fields** | payroll\_run\_id (UUID), billing\_month\_year (VARCHAR), employee\_id (INT), employee\_tin (VARCHAR), base\_salary\_etb (DECIMAL), piece\_rate\_earnings\_etb (DECIMAL), overtime\_earnings\_etb (DECIMAL), gross\_salary\_etb (DECIMAL), employee\_pension\_contribution\_etb (DECIMAL; 7% of base) 9, employer\_pension\_contribution\_etb (DECIMAL; 11% of base) 9, income\_tax\_withheld\_etb (DECIMAL; as per bracket) 9, cash\_advance\_deductions\_etb (DECIMAL), net\_salary\_payable\_etb (DECIMAL) 9, chief\_accountant\_id (INT). |
| **Approval Workflow** | Payroll Lead (Originator) ![][image2] Chief Internal Auditor (Verifier) ![][image2] Chief Financial Officer (Approver). |
| **Accounting/Inventory Impact** | Debit: Salaries Expense Account (GL-5130), Debit: Employer Pension Expense Account (GL-5131); Credit: Net Salary Payable Account (GL-2120), Credit: Tax Withholding Payable Account (GL-2107; MoR Liability), Credit: Pension Fund Payable Account (GL-2125). |

## **Technical Architecture and Regulatory Compliance Integration**

Integrating physical production with tax compliance requires coordinating inventory, manufacturing, and billing systems in real time.  
The digital processing of these documents is structured to support tax audits and general ledger operations.

\+---------------------------------------------------------------------------------------------+  
|                                  Logistics & Operations Layer                               |  
|                                                                                             |  
|                                                      \[Molding & Hydration\]  |  
|         |                                                                      |            |  
|         v                                                                      v            |  
|  Weighbridge Inbound Ticket (1)                                      Daily Mix Optimization |  
|         |                                                            & Batching Slip (11)   |  
|         v                                                                      |            |  
|  Material Inspection / QA Slip (2)                                             v            |  
|         |                                                            Material Requisition   |  
|         v                                                            Model 20 (9)           |  
|  Store Receipt Voucher                                                         |            |  
|  Model 19 (3)                                                                  v            |  
|                                                                      Store Issue Voucher    |  
|                                                                      Model 22 (10)          |  
\+---------------------------------------------------------------------------------------------+  
                                               |  
                                               v  
\+---------------------------------------------------------------------------------------------+  
|                                  Commercial & Dispatch Layer                                |  
|                                                                                             |  
|  \----\> Delivery Challan Model 21 (25) \----\> Outbound Gate Pass (ይለፍ) (26)    |  
|         ^                                                                                   |  
|         |                                                                                   |  
|  Finished Goods Transfer (18)                                                               |  
|         ^                                                                                   |  
|         |                                                                                   |  
|  28-Day Strength Test (17)                                                                  |  
\+---------------------------------------------------------------------------------------------+  
                                               |  
                                               v  
\+---------------------------------------------------------------------------------------------+  
|                                  Financial Compliance Layer                                 |  
|                                                                                             |  
|  \* Supplier Invoice Matching & Purchases (4, 7\)                                             |  
|  \* Withholding Tax Vouchers (2%, 30%, 3%) (5, 6\)                                            |  
|  \* Official MoR Fiscal VAT Invoice Generation (22)                                          |  
|    \- Mandatory 2x2 cm QR Code validation                                        |  
|    \- Integration with MoR E-Service Verification Portal \[7, 23\]                        |  
\+---------------------------------------------------------------------------------------------+

This integrated workflow ensures that every physical movement of raw materials or finished blocks in the yard is backed by a corresponding transaction voucher in the ERP database.  
Matching physical operations with automatic financial journal entries creates a reliable and transparent audit trail.  
This structure helps minimize inventory variances, prevents tax compliance risks, and provides a clear audit history to verify operational costs for the Ethiopian Ministry of Revenues.6

#### **Works cited**

1. (PDF) COMPARATIVE STUDY ON THE COMPRESSIVE STRENGTH AND PRODUCTION COST OF HOLLOW CONCRETE BLOCK (HCB) WITH AND WITHOUT RED ASH IN TEPI TOWN, ETHIOPIA \- ResearchGate, accessed May 26, 2026, [https://www.researchgate.net/publication/331500702\_COMPARATIVE\_STUDY\_ON\_THE\_COMPRESSIVE\_STRENGTH\_AND\_PRODUCTION\_COST\_OF\_HOLLOW\_CONCRETE\_BLOCK\_HCB\_WITH\_AND\_WITHOUT\_RED\_ASH\_IN\_TEPI\_TOWN\_ETHIOPIA](https://www.researchgate.net/publication/331500702_COMPARATIVE_STUDY_ON_THE_COMPRESSIVE_STRENGTH_AND_PRODUCTION_COST_OF_HOLLOW_CONCRETE_BLOCK_HCB_WITH_AND_WITHOUT_RED_ASH_IN_TEPI_TOWN_ETHIOPIA)  
2. HCB Strength and Cost Study in Tepi | PDF | Concrete | Cement \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/751286198/tewodros-getachew](https://www.scribd.com/document/751286198/tewodros-getachew)  
3. Stock Management Manual, accessed May 26, 2026, [https://www.ppa.gov.et/wp-content/uploads/2024/09/Stock\_Management\_Manual\_English.pdf](https://www.ppa.gov.et/wp-content/uploads/2024/09/Stock_Management_Manual_English.pdf)  
4. Airport Check-In Guidelines | Ethiopian Airlines Ethiopia | ET, accessed May 26, 2026, [https://www.ethiopianairlines.com/et/book/check-in/check-in-at-the-airport](https://www.ethiopianairlines.com/et/book/check-in/check-in-at-the-airport)  
5. Tax Invoice QR Code Directive 188/2024 | PDF \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/979738582/Directive-No-188-2024](https://www.scribd.com/document/979738582/Directive-No-188-2024)  
6. Directive No. 1099/2025 A Directive to amend Tax Invoices Usage and Administration Directive No. 165/2017 WHEREAS, it has becom \- Ministry of Justice, accessed May 26, 2026, [https://justice.gov.et/am/?jet\_download=429d95bccbcae361cf1ee02ec1ae4ab12c292151](https://justice.gov.et/am/?jet_download=429d95bccbcae361cf1ee02ec1ae4ab12c292151)  
7. Ethiopia's QR Code Mandate Takes Effect Feb 9, 2025 \- Birr Metrics, accessed May 26, 2026, [https://birrmetrics.com/ethiopias-qr-code-mandate-takes-effect-feb-9-2025/](https://birrmetrics.com/ethiopias-qr-code-mandate-takes-effect-feb-9-2025/)  
8. Ethiopia Phases Out Old Manual Receipts Without QR Codes to Strengthen Tax Compliance, accessed May 26, 2026, [https://www.fanamc.com/english/ethiopia-phases-out-old-manual-receipts-without-qr-codes-to-strengthen-tax-compliance/](https://www.fanamc.com/english/ethiopia-phases-out-old-manual-receipts-without-qr-codes-to-strengthen-tax-compliance/)  
9. PIM-UPSNPFMmanualAugust26-2016Final.docx \- Somali Regional State Bureau of Finance, accessed May 26, 2026, [https://srbofed.gov.et/wp-content/uploads/2019/09/PIM-UPSNPFMmanualAugust26-2016Final.docx](https://srbofed.gov.et/wp-content/uploads/2019/09/PIM-UPSNPFMmanualAugust26-2016Final.docx)  
10. The Withholding Tax Dilemma Hidden in Plain Sight \- Addis Fortune, accessed May 26, 2026, [https://addisfortune.news/the-withholding-tax-dilemma-hidden-in-plain-sight](https://addisfortune.news/the-withholding-tax-dilemma-hidden-in-plain-sight)  
11. Ethiopia Medical Supplies Receipt Form | PDF \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/923568342/APTS-vouchers](https://www.scribd.com/document/923568342/APTS-vouchers)  
12. Fiscal and Non-Fiscal Document Guide | PDF | Receipt | Payments \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/481272746/Fiscal-Documents-Annex-1-FINAL](https://www.scribd.com/document/481272746/Fiscal-Documents-Annex-1-FINAL)  
13. HCB Standard | PDF \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/778023288/HCB-Standard](https://www.scribd.com/document/778023288/HCB-Standard)  
14. IFMIS Print Model20 Report 180326 | PDF \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/1015231433/IFMIS-Print-Model20-Report-180326](https://www.scribd.com/document/1015231433/IFMIS-Print-Model20-Report-180326)  
15. Guidelines for Procurement, Distribution and use of Antiretroviral Drugs in Ethiopia \- EFDA, accessed May 26, 2026, [http://www.efda.gov.et/wp-content/uploads/2019/03/Guidelines\_for\_Procuremen.pdf](http://www.efda.gov.et/wp-content/uploads/2019/03/Guidelines_for_Procuremen.pdf)  
16. Compressive Strength of HCB in Tepi | PDF | Construction Aggregate | Concrete \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/490872946/122340](https://www.scribd.com/document/490872946/122340)  
17. Improving The Performance of Hollow Concrete Block Through the Use of Alternative Aggregate: The case of Adama Town Ethiopia., accessed May 26, 2026, [http://tojqi.net/index.php/journal/article/download/1434/2486/3984](http://tojqi.net/index.php/journal/article/download/1434/2486/3984)  
18. Ethiopian Standard for Hollow Concrete Blocks | PDF \- Scribd, accessed May 26, 2026, [https://www.scribd.com/document/936672376/CES-24-2016Hollow-Concrete-Blocks-Beam-Tile11](https://www.scribd.com/document/936672376/CES-24-2016Hollow-Concrete-Blocks-Beam-Tile11)  
19. How to Post Cash Receipt Voucher (CRV) and Cash or Check Payment Voucher (CPV)?, accessed May 26, 2026, [https://www.youtube.com/watch?v=qfjQqkkkSGM](https://www.youtube.com/watch?v=qfjQqkkkSGM)  
20. Full article: Inventory management performance for laboratory commodities in public hospitals of Jimma zone, Southwest Ethiopia \- Taylor & Francis, accessed May 26, 2026, [https://www.tandfonline.com/doi/full/10.1186/s40545-020-00251-1](https://www.tandfonline.com/doi/full/10.1186/s40545-020-00251-1)  
21. (PDF) Assessment of inventory and store management practices of pharmaceuticals in public health centers and hospitals of Dessie Town, Ethiopia \- ResearchGate, accessed May 26, 2026, [https://www.researchgate.net/publication/340195647\_Assessment\_of\_inventory\_and\_store\_management\_practices\_of\_pharmaceuticals\_in\_public\_health\_centers\_and\_hospitals\_of\_Dessie\_Town\_Ethiopia](https://www.researchgate.net/publication/340195647_Assessment_of_inventory_and_store_management_practices_of_pharmaceuticals_in_public_health_centers_and_hospitals_of_Dessie_Town_Ethiopia)  
22. federal income tax proclamation \- Ethiopian Legal Brief, accessed May 26, 2026, [https://chilot.files.wordpress.com/2016/06/incom-tax-proclamation-english.pdf](https://chilot.files.wordpress.com/2016/06/incom-tax-proclamation-english.pdf)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAAAhUlEQVR4XmNgGAWjgCTAAcRpQMyDLkEqYATiViA2RpcgB4AM6QViFnQJUgHIVQVAHAdlw4EAEEuSiOWAeD4QTwZiPiBm4AbiaiCeRQbeAcRfgbiZgQJgAsSrgVgGXYIUIAzEi4FYHl2CVJAFxBHogqQCUIKcCsTS6BKkAlB080LpUUACAABjSBNDIJEBIwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAWCAYAAADwza0nAAAAsElEQVR4XmNgGAUEgSMQnwDiCCBmRZMjCDiBOAmILwBxMhBzo0oTBiAbQTafAeIaIOZDlSYMmIHYCYgPA3E3EAujShMGjEBsDsT7gXgKEEuiShMG7EBcB8RPgFgFTQ4rQA60fAYiAg2kAKTwHAOR0QQKRVBoguLVnwESSHgByNMgz4MCwYqBCA0g4APEG4FYjwESioMYgEJMnAHiT0JYjAHJ/wZAPItI3MtARuqhHAAAUy8ZXUJCyYEAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA/CAYAAABdEJRVAAAE8klEQVR4Xu3d6+ufYxwH8EtYjHLYwhoPLDkkhzKemAeSHIokk5IopORUQiQ5ljxxqElSSMhSlEO2yX7akvJMkUixPPEHTCGH69113fvevmO23/b7/VivV7373tf9vb/fx5+uw+cuBQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIDt/VbzR//ct+bZPv6l5pqa42p+6PdO6b8BAGAeraiZqTl4dO+nmv1G43Nq9hmNAQCYR0trvq9Z1sfnlzajNhRwl9Vc368BAFgAKcyGgi3Xz43GkSXSJf0aAIAFsrXmjJo1pRVtMzWnlbZ/7cDJY7tk8fQNAABm79fS9qllOTTeq1lZ89C2J3bNITUfTN8EAGD2cgL0q9H45ZrvSpthG+TQwfs1p9ecWrO6tOXSyCzc2prLaw6oWV+zpeaY/v0TpRWDOciQJdeza27u3wEAsBO+KZPiKu4p2+9bO6K0gm1Vzbr+mcMIV/X7KdTe6c9+VHNmaQcavqi5uubC0v5jc2nLr+NTqQAA/Ivp/mrLp8aDDTWH1WwsrRi7qbTZuPtK+82m/tzwfQqz8cxdDP8BAMAcyMzZ7TWf9s/sVbug5pWa50vbt5ZZtBRlKeKyjHpbaTNsKd4iM3IAAMyRFGCZHRs+B/v3z0X986DRvTh0dJ23KQAAzKu3ar6tOaFMWmJENvI/1q8BAFgg2aifmaQsEWZ5MEt/ea1TZEkwe7x2xjAzFeeNrgEA2AOOrXmwXz9T2qnIeLhM9m3tSFpdvD4az/WsXGb+/ssBANjj0gLj6H6dVzplHHf3z6dL26D/Wh/Hi6U1pT28tCXVH0vrbXZUaYXe4Mmat8s/7/u6Yge5qMz+LQUAAHuVLHuu6Nc/lzZDlmXSoels3iDwZWmFWVxa2l639CnL7/L7zMxlI/91NZ/0584qraDL/fQwAwBgN+QUZNpZRBrIJoPMuA3LnFki/Xx0PzbWnNSvszyathd5LkVe5DRmijwAAOZICrLsc4vMrKVfWZY63y2tOJupubd/n5OmWRLNDN1TNXfUvNC/29OyX+yW0TiHJPJqqUGWaNN3DQBgr5eeZNOyJy1LnTE9Ize+nsvXN6VgG2b5IgVbTrkO7i+Tl8EDALAAfi/ttVLxaGkzekMBl6XZk/s1AAALZGuZFGyPl7YcOoxzUGKYAQQAYIGkBclMmSx75qDDh6Ut4e5sw9/dlWbDef8oAAB/47PSirbVfbysZlPNA9ueaIa2IukdF3kuByaurbmktKXTG0prSXJ8zRv9ubi45qXS+tSlH92tpR2ieLW0vXrra7aU9sYIAACmzJS2j21orptCLAcRxm9diDQAzoGE9JFbWfNxaUXcIzXX16wrrV9c3qd6Z2mFW+Sk61392RtLW2b9uo+HvXLpPzdfs3kAAP872a82bhmSE6kpwqb3rr1Z2iGESG+4c0ffLS+TpsGZgctvN/RxirIUbYOhH92RpRWLkZYnS4cHAAD4q+xZmy6WMlM2bU3/zH6zzWXyftQsha4qrdBLoTbMlKV3W2bexjNnJ9asLa0BcJLrK0tbGk1Rl/8GAGCWUoyNC7nsPRtm4RaN7g/GfeeWlElfufH9xaN741k4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2EV/Ap8TxgZgcCIuAAAAAElFTkSuQmCC>