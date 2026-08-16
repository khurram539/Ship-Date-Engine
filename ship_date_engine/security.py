def validate_file_content(
    content: str,
    max_length: int = Config.MAX_FIELD_LENGTH,
) -> Tuple[bool, list[str]]:
    """
    Validate that file content doesn't contain dangerous patterns.
    
    Args:
        content: File content to validate
        max_length: Maximum allowed content length
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Check length
    if len(content) > max_length:
        warnings.append(
            f"Content exceeds maximum length of {max_length} characters"
        )
    
    # Check for potential SQL injection patterns
    dangerous_patterns = [
        r"(?i)\b(drop\s+table|delete\s+from|insert\s+into|update\s+)\b",
        r"(?i)\b(select|exec|execute|xp_cmdshell)\b",
        r"(?i)0x[0-9a-f]+",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content):
            warnings.append("Potentially dangerous SQL patterns detected")
            break
    
    return len(warnings) == 0, warnings
