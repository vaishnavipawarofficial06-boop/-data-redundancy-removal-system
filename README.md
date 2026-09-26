# Data Redundancy Removal System

## Overview

The Data Redundancy Removal System detects duplicate and similar
records before storing data in the database.

## Objectives

- Validate incoming data
- Normalize data
- Detect exact duplicates
- Detect similar records
- Prevent duplicate data
- Store only unique records
- Improve database accuracy

## Technologies

- Python
- FastAPI
- SQLite
- SQLAlchemy
- Pydantic
- RapidFuzz
- Pytest

## System Flow

Input Data
↓
Validation
↓
Normalization
↓
Exact Duplicate Check
↓
Similarity Check
↓
Classification
↓
Unique Data → Database
Duplicate → Rejected
Possible Duplicate → Review

## Run Project

Install dependencies:

```bash
pip install -r requirements.txt