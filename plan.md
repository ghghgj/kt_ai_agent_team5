# RAG 구현 계획 (file1.pdf)

## 1. 개요

`file1.pdf` 문서를 기반으로 질문-답변이 가능한 RAG(Retrieval-Augmented Generation) 시스템을 구축합니다.

---

## 2. 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| PDF 파싱 | `PyMuPDFLoader` (langchain-community) |
| 텍스트 분할 | `RecursiveCharacterTextSplitter` |
| 임베딩 모델 | OpenAI `text-embedding-3-small` |
| 벡터 DB | FAISS (로컬 저장) |
| LLM | OpenAI `gpt-4o-mini` |
| 프레임워크 | LangChain |
| 설정 관리 | `.env` (python-dotenv) |

---

## 3. 구현 단계

### Step 1. PDF 로드
- `PyMuPDFLoader`로 `data/pdf/file1.pdf` 읽기
- 페이지 메타데이터(페이지 번호, 파일명) 포함

### Step 2. 텍스트 청크 분할
- `chunk_size=500`, `chunk_overlap=50` 으로 분할
- 문장 경계를 최대한 보존하는 `RecursiveCharacterTextSplitter` 사용

### Step 3. 임베딩 & 벡터스토어 생성
- OpenAI `text-embedding-3-small`로 각 청크 임베딩
- FAISS 인덱스 생성 후 `faiss_index_file1/` 폴더에 로컬 저장
- 재실행 시 기존 인덱스 재사용 (불필요한 API 호출 방지)

### Step 4. 검색기(Retriever) 설정
- 유사도 기반 Top-K 검색 (`k=4`)

### Step 5. QA 체인 구성 (멀티턴)
- `ConversationalRetrievalChain` 사용
- 대화 히스토리를 LLM에 전달하여 문맥 이해 가능
- 이전 질문을 참고해 검색 쿼리 자동 재작성 (Condense Question)
- `ConversationBufferMemory`로 대화 기록 유지
- Hallucination 방지: context에 없는 내용은 "모르겠습니다" 출력

### Step 6. 사용자 인터페이스 (Gradio)
- `gradio` 웹 UI로 질문 입력 → 답변 + 참고 페이지 번호 출력
- `gr.ChatInterface` 사용하여 대화 히스토리 화면에 표시
- 로컬 브라우저에서 접근 (`http://localhost:7860`)

---

## 4. 생성 파일

```
kt_ai_agent_team5/
├── rag.py                  ← RAG 메인 코드
└── faiss_index_file1/      ← 벡터스토어 (실행 후 자동 생성)
    ├── index.faiss
    └── index.pkl
```

---

## 5. 실행 방법

```bash
python rag.py
```

- **첫 실행**: PDF 파싱 → 임베딩 → FAISS 인덱스 생성 (수 분 소요)
- **재실행**: 저장된 인덱스 즉시 로드
- 실행 후 브라우저에서 `http://localhost:7860` 접속

---

## 6. 출력 예시

브라우저에서 채팅 UI로 질문 입력:

```
사용자: 문서의 주요 내용은 무엇인가요?
AI:     ...내용 답변...
        📄 참고 페이지: 3, 7, 12, 15
```

---

## 7. 검토 포인트

- [ ] chunk_size / chunk_overlap 값 조정 여부
- [ ] 검색 Top-K 값 (현재 k=4) 변경 여부
- [x] 인터페이스 방식: Gradio UI (`gr.ChatInterface`)
- [ ] 프롬프트 언어 (현재 한국어) 변경 여부
