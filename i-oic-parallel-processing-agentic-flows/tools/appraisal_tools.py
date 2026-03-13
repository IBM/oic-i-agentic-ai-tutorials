"""
Employee Appraisal Tools for watsonx Orchestrate

These tools work together to process employee appraisals in parallel:
1. read_employee_data - Reads Excel/CSV and chunks data
2. calculate_employee_appraisal - Calculates appraisal for one employee
3. write_appraisal_results - Writes all results to output file
"""

from typing import List, Dict, Any
import pandas as pd
import requests
import tempfile
import os
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool
import io


# ============================================================================
# DATA MODELS
# ============================================================================

class EmployeeData(BaseModel):
    """Single employee data for appraisal calculation"""
    employee_id: str
    employee_name: str
    department: str
    role: str
    current_salary: float
    years_of_experience: float
    years_in_company: float
    target_revenue: float
    achieved_revenue: float


class AppraisalResult(BaseModel):
    """Result of appraisal calculation for one employee"""
    employee_id: str
    employee_name: str
    current_salary: float
    revenue_score: float
    experience_bonus: float
    loyalty_bonus: float
    appraisal_score: float
    rating: str
    increment_percentage: float
    new_salary: float
    salary_increase: float


# ============================================================================
# TOOL 1: READ AND CHUNK EMPLOYEE DATA
# ============================================================================

@tool(
    name="read_employee_data",
    description="Reads employee data from uploaded Excel or CSV file URL and returns list of employee records for appraisal processing"
)
def read_employee_data(file_path: str) -> List[EmployeeData]:
    """
    Reads employee data from uploaded Excel or CSV file.
    
    In watsonx Orchestrate workflows, uploaded files are provided as S3 signed URLs.
    This tool downloads the file from the URL and processes it.
    
    Args:
        file_path (str): S3 signed URL to the uploaded Excel (.xlsx) or CSV (.csv) file.
    
    Returns:
        List[EmployeeData]: List of employee data objects ready for appraisal calculation.
    """
    print(f"[DEBUG] Starting to read employee data from URL: {file_path[:100]}...")
    
    # Download file from S3 URL
    print(f"[DEBUG] Downloading file from S3 URL...")
    try:
        response = requests.get(file_path, timeout=30)
        response.raise_for_status()
        
        # Determine file extension from URL or content-type
        if '.xlsx' in file_path or 'spreadsheet' in response.headers.get('content-type', ''):
            file_extension = '.xlsx'
        elif '.csv' in file_path or 'csv' in response.headers.get('content-type', ''):
            file_extension = '.csv'
        else:
            # Default to xlsx
            file_extension = '.xlsx'
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(response.content)
            temp_file_path = tmp_file.name
        
        print(f"[DEBUG] Downloaded file to: {temp_file_path}")
        
        # Read file based on extension
        if file_extension == '.xlsx':
            print(f"[DEBUG] Reading Excel file format")
            df = pd.read_excel(temp_file_path)
        else:  # .csv
            print(f"[DEBUG] Reading CSV file format")
            df = pd.read_csv(temp_file_path)
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        print(f"[DEBUG] Cleaned up temporary file")
        
    except Exception as e:
        print(f"[DEBUG] Error processing file: {str(e)}")
        raise ValueError(f"Failed to process file from URL: {str(e)}")
    
    print(f"[DEBUG] Successfully read file with {len(df)} rows")
    
    # Convert to list of EmployeeData objects
    employees = []
    for idx, row in df.iterrows():
        employee = EmployeeData(
            employee_id=str(row['employee_id']),
            employee_name=str(row['employee_name']),
            department=str(row['department']),
            role=str(row['role']),
            current_salary=float(row['current_salary']),  # type: ignore[arg-type]
            years_of_experience=float(row['years_of_experience']),  # type: ignore[arg-type]
            years_in_company=float(row['years_in_company']),  # type: ignore[arg-type]
            target_revenue=float(row['target_revenue']),  # type: ignore[arg-type]
            achieved_revenue=float(row['achieved_revenue'])  # type: ignore[arg-type]
        )
        employees.append(employee)
    
    print(f"[DEBUG] Converted {len(employees)} employee records to EmployeeData objects")
    print(f"[DEBUG] Sample employees: {[e.employee_name for e in employees[:3]]}")
    
    return employees


# ============================================================================
# TOOL 2: CALCULATE APPRAISAL FOR ONE EMPLOYEE
# ============================================================================

@tool(
    name="calculate_employee_appraisal",
    description="Calculates appraisal score, rating, and salary increment for a single employee based on revenue achievement, experience, and loyalty"
)
def calculate_employee_appraisal(employee: EmployeeData) -> AppraisalResult:
    """
    Calculates comprehensive appraisal for one employee.
    
    Args:
        employee (EmployeeData): Employee data including revenue targets and achievements.
    
    Returns:
        AppraisalResult: Complete appraisal calculation with scores, rating, and increment.
    """
    print(f"[DEBUG] Calculating appraisal for: {employee.employee_name} ({employee.employee_id})")
    
    # 1. REVENUE ACHIEVEMENT SCORE (0-100)
    if employee.target_revenue > 0:
        revenue_achievement_pct = (employee.achieved_revenue / employee.target_revenue) * 100
    else:
        revenue_achievement_pct = 100.0
    
    # Score calculation with different ranges
    if revenue_achievement_pct < 50:
        revenue_score = revenue_achievement_pct * 0.5
    elif revenue_achievement_pct < 80:
        revenue_score = 25 + ((revenue_achievement_pct - 50) * 1.17)
    elif revenue_achievement_pct < 100:
        revenue_score = 60 + ((revenue_achievement_pct - 80) * 1.25)
    elif revenue_achievement_pct < 120:
        revenue_score = 85 + ((revenue_achievement_pct - 100) * 0.75)
    else:
        revenue_score = 100.0
    
    # 2. EXPERIENCE BONUS (0-15%)
    if employee.years_of_experience >= 20:
        experience_bonus = 15.0
    elif employee.years_of_experience >= 15:
        experience_bonus = 12.0
    elif employee.years_of_experience >= 10:
        experience_bonus = 9.0
    elif employee.years_of_experience >= 7:
        experience_bonus = 6.0
    elif employee.years_of_experience >= 5:
        experience_bonus = 4.0
    elif employee.years_of_experience >= 3:
        experience_bonus = 2.0
    else:
        experience_bonus = 0.0
    
    # 3. LOYALTY BONUS (0-15%)
    if employee.years_in_company >= 15:
        loyalty_bonus = 15.0
    elif employee.years_in_company >= 10:
        loyalty_bonus = 12.0
    elif employee.years_in_company >= 7:
        loyalty_bonus = 9.0
    elif employee.years_in_company >= 5:
        loyalty_bonus = 6.0
    elif employee.years_in_company >= 3:
        loyalty_bonus = 4.0
    elif employee.years_in_company >= 1:
        loyalty_bonus = 2.0
    else:
        loyalty_bonus = 0.0
    
    # 4. CALCULATE FINAL APPRAISAL SCORE
    appraisal_score = min(revenue_score + experience_bonus + loyalty_bonus, 130.0)
    
    # 5. DETERMINE RATING & INCREMENT
    if appraisal_score >= 110:
        rating = "Outstanding"
        increment_percentage = 15.0
    elif appraisal_score >= 95:
        rating = "Exceeds Expectations"
        increment_percentage = 12.0
    elif appraisal_score >= 80:
        rating = "Meets Expectations"
        increment_percentage = 8.0
    elif appraisal_score >= 60:
        rating = "Needs Improvement"
        increment_percentage = 4.0
    else:
        rating = "Unsatisfactory"
        increment_percentage = 0.0
    
    # 6. CALCULATE NEW SALARY
    new_salary = employee.current_salary * (1 + increment_percentage / 100)
    salary_increase = new_salary - employee.current_salary
    
    result = AppraisalResult(
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        current_salary=round(employee.current_salary, 2),
        revenue_score=round(revenue_score, 2),
        experience_bonus=round(experience_bonus, 2),
        loyalty_bonus=round(loyalty_bonus, 2),
        appraisal_score=round(appraisal_score, 2),
        rating=rating,
        increment_percentage=round(increment_percentage, 2),
        new_salary=round(new_salary, 2),
        salary_increase=round(salary_increase, 2)
    )
    
    print(f"[DEBUG] Completed appraisal for {employee.employee_name}: Score={result.appraisal_score}%, Rating={result.rating}, Increment={result.increment_percentage}%")
    
    return result


# ============================================================================
# TOOL 3: GENERATE EXCEL FILE (RETURNS BYTES FOR DOWNLOAD)
# ============================================================================

@tool(
    name="generate_appraisal_excel",
    description="Generates a downloadable Excel file with appraisal results and returns it as bytes"
)
def generate_appraisal_excel(results: List[Any]) -> bytes:
    """
    Generates Excel file with appraisal results and returns as bytes for download.
    
    Args:
        results (List[Any]): List of appraisal results (can be dicts or AppraisalResult objects).
    
    Returns:
        bytes: Excel file content as bytes for download.
    """
    print(f"[DEBUG] Generating Excel file for {len(results)} appraisal results")
    
    # Convert results to DataFrame
    data = []
    for result in results:
        # Handle both dict and AppraisalResult object
        if isinstance(result, dict):
            data.append({
                'Employee ID': result.get('employee_id', ''),
                'Employee Name': result.get('employee_name', ''),
                'Current Salary': result.get('current_salary', 0),
                'Revenue Score': result.get('revenue_score', 0),
                'Experience Bonus': result.get('experience_bonus', 0),
                'Loyalty Bonus': result.get('loyalty_bonus', 0),
                'Appraisal Score': result.get('appraisal_score', 0),
                'Rating': result.get('rating', ''),
                'Increment %': result.get('increment_percentage', 0),
                'New Salary': result.get('new_salary', 0),
                'Salary Increase': result.get('salary_increase', 0)
            })
        else:
            # AppraisalResult object
            data.append({
                'Employee ID': result.employee_id,
                'Employee Name': result.employee_name,
                'Current Salary': result.current_salary,
                'Revenue Score': result.revenue_score,
                'Experience Bonus': result.experience_bonus,
                'Loyalty Bonus': result.loyalty_bonus,
                'Appraisal Score': result.appraisal_score,
                'Rating': result.rating,
                'Increment %': result.increment_percentage,
                'New Salary': result.new_salary,
                'Salary Increase': result.salary_increase
            })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Appraisal Results', index=False)
        
        # Get workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets['Appraisal Results']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    # Get bytes
    excel_bytes = output.getvalue()
    
    print(f"[DEBUG] Generated Excel file: {len(excel_bytes)} bytes")
    print(f"[DEBUG] Rating distribution:")
    rating_counts = {}
    for result in results:
        rating = result.get('rating', '') if isinstance(result, dict) else result.rating
        rating_counts[rating] = rating_counts.get(rating, 0) + 1
    for rating, count in sorted(rating_counts.items()):
        print(f"[DEBUG]   - {rating}: {count} employees")
    
    return excel_bytes


# ============================================================================
# TOOL 4: FORMAT EMPLOYEE DATA FOR PREVIEW
# ============================================================================

