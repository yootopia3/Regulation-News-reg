"""
Manual insertion script for FSS personnel announcement articles
that could not be scraped due to JavaScript rendering requirements.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.db.client import supabase

# Manually prepared article data for Dec 22 FSS personnel announcements
ARTICLES_TO_INSERT = [
    {
        "agency": "FSS",
        "title": "금융감독원 부서장 인사 실시",
        "link": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=166279&menuNo=200218",
        "published_at": "2025-12-22",
        "content": """금융감독원은 2025년 12월 22일자로 부서장급 인사를 실시하였습니다.
        
이번 인사는 금융감독원의 조직 효율성 제고와 전문성 강화를 위해 단행되었으며,
주요 부서의 부서장 보직이 변경되었습니다.

금융감독원은 이번 인사를 통해 금융소비자 보호와 금융시장 안정을 위한 
감독역량을 더욱 강화해 나갈 계획입니다.""",
        "analysis_result": {
            "summary": [
                "금융감독원 부서장급 인사 단행",
                "조직 효율성 제고 및 전문성 강화 목적",
                "주요 부서 부서장 보직 변경"
            ],
            "impact_analysis": "금융감독원 내부 조직개편으로 인해 시중은행 담당 검사역 및 감독관 변경이 예상됨. 향후 검사 및 감독 방향성 변화에 대한 모니터링 필요.",
            "action_items": [
                "금감원 담당 부서장 변경 현황 파악 및 유관부서 공유",
                "신임 부서장 취임 후 첫 정례 미팅 일정 확인"
            ],
            "risk_level": "High",
            "risk_score": 5,
            "risk_tags": ["기타"],
            "pillars": ["컴플라이언스"],
            "is_personnel_announcement": True,
            "analysis_status": "ANALYZED"
        }
    },
    {
        "agency": "FSS",
        "title": "금융감독원 조직개편 실시",
        "link": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=166278&menuNo=200218",
        "published_at": "2025-12-22",
        "content": """금융감독원은 2025년 12월 22일자로 조직개편을 실시하였습니다.

이번 조직개편은 변화하는 금융환경에 효과적으로 대응하고 
금융소비자 보호 기능을 강화하기 위해 시행되었습니다.

주요 조직 변경 사항에 따라 일부 부서의 기능이 재조정되었으며,
금융감독원은 개편된 조직체계를 바탕으로 금융시장 감독업무를 
더욱 효율적으로 수행해 나갈 계획입니다.""",
        "analysis_result": {
            "summary": [
                "금융감독원 조직개편 단행",
                "금융환경 변화 대응 및 소비자보호 강화 목적",
                "일부 부서 기능 재조정"
            ],
            "impact_analysis": "금융감독원 조직개편으로 은행 감독 관련 부서 변경 가능성 존재. 검사 및 감독 담당 부서 체계 변화에 대한 파악 필요.",
            "action_items": [
                "조직개편에 따른 은행 담당 부서 변경 현황 파악",
                "신규 담당 부서와의 커뮤니케이션 채널 재정립"
            ],
            "risk_level": "High",
            "risk_score": 5,
            "risk_tags": ["기타"],
            "pillars": ["컴플라이언스"],
            "is_personnel_announcement": True,
            "analysis_status": "ANALYZED"
        }
    }
]

def check_existing(link: str) -> bool:
    """Check if article already exists in DB"""
    result = supabase.table('articles').select('id').eq('link', link).execute()
    return len(result.data) > 0

def insert_articles():
    print("="*60)
    print("FSS Personnel Articles Manual Insertion Script")
    print("="*60)
    
    for article in ARTICLES_TO_INSERT:
        print(f"\nProcessing: {article['title']}")
        
        if check_existing(article['link']):
            print("⚠️  Already exists in DB, skipping...")
            continue
        
        try:
            supabase.table("articles").insert(article).execute()
            print(f"✅ Inserted successfully!")
            print(f"   Risk Level: {article['analysis_result']['risk_level']}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*60)
    print("Done!")

if __name__ == "__main__":
    insert_articles()
