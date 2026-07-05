# Corpus Inventory

이 파일은 `data/docs/*.md`의 front matter를 기준으로 정리한 전체 corpus inventory입니다. README에는 대표 문서와 요약만 두고, 누락 없는 전체 목록은 여기에서 확인합니다.

| id | trust | publisher | review | why selected |
| --- | --- | --- | --- | --- |
| `distractor_delivery_area` | untrusted | local-controlled-fixture | intentionally_irrelevant | 배송·반품·상품 수령 단어를 포함한 무관 문서가 환불 질문을 방해하는지 확인하기 위해 |
| `distractor_marketing_campaign` | untrusted | local-controlled-fixture | intentionally_irrelevant | 이메일·고객·동의 같은 단어를 포함하지만 개인정보 처리 답변 근거가 아닌 distractor |
| `distractor_membership_tiers` | untrusted | local-controlled-fixture | intentionally_irrelevant | 환불·상담과 무관한 등급/혜택 문서가 검색 후보에 끼는지 확인하기 위해 |
| `distractor_mobile_app_release` | untrusted | local-controlled-fixture | intentionally_irrelevant | 개인정보·알림·접속기록과 비슷한 단어가 있는 무관한 제품 문서 distractor |
| `distractor_server_maintenance` | untrusted | local-controlled-fixture | intentionally_irrelevant | 운영시간·접수·응답 지연 단어가 상담 정책 검색에 섞이는지 확인하기 위한 distractor |
| `easylaw_internet_refund` | trusted | 법제처 찾기쉬운 생활법령정보 | human_checked_from_official_source | 환불·청약철회 질문은 상담 RAG에서 자주 나오는 고위험 답변 영역이고, 법제처 생활법령은 일반 사용자가 이해하기 쉬운 공식 설명을 제공하기 때문 |
| `easylaw_secondhand_transaction` | trusted | 법제처 찾기쉬운 생활법령정보 | human_checked_from_official_source | 전자상거래와 달리 개인 간 거래는 일반 청약철회권이 제한될 수 있음을 구분하기 위해 |
| `kca_consumer_consultation_trends` | trusted | 공공데이터포털 / 한국소비자원 | human_checked_from_official_source | 실제 상담 수요와 질문 주제를 정하는 근거가 필요해서, 1372 소비자상담센터 기반 공식 통계 메타데이터를 포함함 |
| `kca_damage_relief_exclusions` | trusted | 한국소비자원 | human_checked_from_official_source | 피해구제 신청이 가능한 사건과 제외되는 사건을 구분하기 위해 |
| `kca_damage_relief_process` | trusted | 한국소비자원 | human_checked_from_official_source | 상담 현황 데이터만으로는 실제 민원 처리 흐름을 설명하기 어려워, 상담 이후 피해구제 신청·사업자 통보·사실조사·합의권고 흐름을 공식 절차 문서로 보강함 |
| `kca_dispute_resolution_standards` | trusted | 한국소비자원 | human_checked_from_official_source | 전자상거래 청약철회 외에도 수리·교환·환급 같은 일반 소비자분쟁 질문이 자주 발생하므로, 공식 분쟁해결 기준의 적용 범위를 corpus에 추가함 |
| `kca_mediation_process` | trusted | 한국소비자원 | human_checked_from_official_source | 피해구제 이후 조정 단계와 합의권고 질문을 분리해서 평가하기 위해 |
| `kca_online_odr_features` | trusted | 한국소비자원 | human_checked_from_official_source | 온라인 피해구제에서 가능한 조회·취하·자료제출 기능을 평가하기 위해 |
| `kca_quality_warranty_periods` | trusted | 한국소비자원 | human_checked_from_official_source | 수리·교환·부품 보유 기간 질문의 공식 근거를 보강하기 위해 |
| `privacy_consent_guide` | trusted | 개인정보보호위원회 | human_checked_from_official_source | 개인정보 수집 동의 질문에서 필수/선택 동의와 명확한 고지를 구분하기 위해 |
| `privacy_overseas_transfer_note` | trusted | 개인정보보호위원회 | human_checked_from_official_source | 해외 클라우드와 국외 이전 질문에서 동의·법적 근거·고지를 확인하기 위해 |
| `privacy_policy_guide` | trusted | 개인정보보호위원회 개인정보 포털 | human_checked_from_official_source | 개인정보 처리방침은 AI 상담·운영 서비스가 반드시 근거를 확인해야 하는 준법 영역이고, 개인정보보호위원회 지침은 작성 항목을 공식적으로 설명하기 때문 |
| `privacy_safety_measures` | trusted | 개인정보보호위원회 개인정보 포털 | human_checked_from_official_source | 개인정보 처리방침 문서가 “무엇을 공개해야 하는지”를 다룬다면, 이 문서는 실제 시스템 운영에서 접근권한·접속기록·암호화 같은 보호조치를 묻는 질문을 다루기 위해 선택함 |
| `privacy_training_obligation` | trusted | 개인정보보호위원회 개인정보 포털 | human_checked_from_official_source | 개인정보 취급자 교육과 내부 관리 질문을 답변 범위에 포함하기 위해 |
| `stale_privacy_policy_2020` | untrusted | unknown | stale_unverified | 오래된 개인정보 보관 관행이 최신 처리방침·보유기간 지침과 충돌하는지 보기 위해 |
| `stale_refund_policy_2021` | untrusted | unknown | stale_unverified | 오래된 환불 기준이 최신 공식 문서보다 앞서 검색될 때 stale risk를 측정하기 위해 |
| `trusted_distractor_event_refund` | trusted | local-controlled-fixture | intentionally_irrelevant | 환불이라는 동일 단어를 쓰지만 전자상거래 청약철회와 다른 도메인의 distractor를 넣기 위해 |
| `trusted_distractor_library_rules` | trusted | local-controlled-fixture | intentionally_irrelevant | 상담 운영시간·이메일·접수 같은 단어를 포함한 무관 문서가 검색 후보에 끼는지 확인하기 위해 |
| `trusted_distractor_parking_policy` | trusted | local-controlled-fixture | intentionally_irrelevant | 환불·개인정보 질문과 무관한 trusted 문서가 검색 품질을 흐리는지 확인하기 위한 distractor |
| `trusted_distractor_training_attendance` | trusted | local-controlled-fixture | intentionally_irrelevant | 교육·개인정보보호교육 질문과 섞일 수 있는 무관한 출석 기준 distractor |
| `untrusted_chatbot_script_poison` | untrusted | unknown | intentionally_untrusted | 상담 시간·이메일 질문에서 악성 지시문을 포함한 운영 스크립트가 검색될 때를 평가하기 위해 |
| `untrusted_coupon_refund_note` | untrusted | unknown | unverified | 행사·쿠폰 환불 같은 유사 환불 문서가 전자상거래 청약철회 답변을 흐리는지 확인하기 위해 |
| `untrusted_mediation_blog` | untrusted | unknown | unverified | 피해구제·조정 절차와 유사하지만 공식 절차와 다른 내용을 담은 source conflict 문서 |
| `untrusted_overseas_transfer_memo` | untrusted | unknown | unverified | 해외 클라우드 사용에 대한 비공식 주장과 공식 국외이전 고지 기준의 충돌을 평가하기 위해 |
| `untrusted_privacy_memo` | untrusted | unknown | intentionally_untrusted | 개인정보 보유와 처리방침 안내를 무시하라는 비공식 지시가 검색 후보에 들어왔을 때 답변에서 제외되는지 확인하기 위함 |
| `untrusted_privacy_minimization_blog` | untrusted | unknown | unverified | 개인정보 동의·최소수집 질문에서 공식 안내와 비공식 요약이 섞이는지 확인하기 위해 |
| `untrusted_refund_blog` | untrusted | unknown | intentionally_untrusted | 공식 환불 기준과 충돌하는 출처 불명 주장을 넣어 검색 단계에서 위험 문서를 감지하고 차단하는지 확인하기 위함 |
| `untrusted_refund_forum` | untrusted | unknown | unverified | 악성 지시문은 없지만 공식 청약철회 기준과 충돌하는 비공식 정보를 넣어 source conflict 실패 모드를 측정하기 위함 |
| `untrusted_shipping_delay_forum` | untrusted | unknown | unverified | 배송 지연과 청약철회 기준을 혼동시키는 conflict distractor |
| `untrusted_support_hours_note` | untrusted | unknown | unverified | 공식 문서만 허용할 때 안전성은 올라가지만 답변 커버리지가 줄어드는지 측정하기 위한 비공식-only 문서 |
