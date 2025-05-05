"""Analysis utility functions."""

def generate_analysis_synthesis(company_name: str, score: float) -> str:
    """
    Generate an analysis synthesis based on the company's overall score.
    
    Args:
        company_name: The name of the company being analyzed
        score: The overall score from 0-100
        
    Returns:
        A synthesis statement customized to the score range
    """
    # Define score ranges and corresponding synthesis messages
    if score < 10:
        return f"{company_name}'s AEO report obtained a critically low score of {score:.1f}. Immediate action is needed as your brand is likely invisible to AI chatbots. Following our detailed recommendations is essential to establish any presence."
    
    elif score < 20:
        return f"{company_name}'s AEO report obtained a very low score of {score:.1f}. Your brand has minimal to no visibility to AI systems. Significant improvements are needed across all areas for AI chatbots to recognize and mention your company."
    
    elif score < 30:
        return f"{company_name}'s AEO report obtained a low score of {score:.1f}. There are many aspects missing that need to be reviewed if you want AI chatbots to mention your brand and its products. Focus on implementing our key recommendations."
    
    elif score < 40:
        return f"{company_name}'s AEO report obtained a below average score of {score:.1f}. While some elements are in place, your brand still lacks sufficient visibility to AI systems. Addressing our recommendations will help improve your AI visibility."
    
    elif score < 50:
        return f"{company_name}'s AEO report obtained a moderate score of {score:.1f}. Your brand has basic visibility to AI chatbots, but considerable improvements can be made to increase mentions and accuracy of information."
    
    elif score < 60:
        return f"{company_name}'s AEO report obtained a fair score of {score:.1f}. Your company has established a foundation for AI visibility. Implementing our suggested optimizations will significantly enhance your presence in AI responses."
    
    elif score < 70:
        return f"{company_name}'s AEO report obtained a good score of {score:.1f}. Your brand is being mentioned by AI chatbots, though there's still room for improvement. Follow our recommendations to enhance the frequency and context of mentions."
    
    elif score < 80:
        return f"{company_name}'s AEO report obtained a very good score of {score:.1f}. Your company has implemented many effective strategies and is regularly mentioned by AI systems. Our suggestions will help you refine your approach further."
    
    elif score < 90:
        return f"{company_name}'s AEO report obtained an excellent score of {score:.1f}. This shows that most strategies are correctly implemented and your company is frequently mentioned in AI chatbots. Follow our suggestions to maximize your AI visibility."
    
    else:
        return f"Exceptional! {company_name}'s AEO report obtained an outstanding score of {score:.1f}. Your company has mastered AI visibility strategies and is prominently featured in AI responses. Our minor suggestions will help maintain this exceptional performance." 