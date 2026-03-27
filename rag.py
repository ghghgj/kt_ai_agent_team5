import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
import gradio as gr

load_dotenv()

PDF_PATH = "data/pdf/file1.pdf"
FAISS_INDEX_PATH = "faiss_index_file1"


def build_vectorstore():
    print("PDF 로딩 중...")
    loader = PyMuPDFLoader(PDF_PATH)
    docs = loader.load()
    print(f"  총 {len(docs)}페이지 로드 완료")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    print(f"  청크 수: {len(chunks)}")

    print("임베딩 및 벡터스토어 생성 중...")
    embeddings = OpenAIEmbeddings(model=os.getenv("EMB_MODEL_NAME", "text-embedding-3-small"))
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"  벡터스토어 저장 완료: {FAISS_INDEX_PATH}/")
    return vectorstore


def load_vectorstore():
    print(f"기존 벡터스토어 로드: {FAISS_INDEX_PATH}/")
    embeddings = OpenAIEmbeddings(model=os.getenv("EMB_MODEL_NAME", "text-embedding-3-small"))
    return FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)


def build_chain(vectorstore):
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0,
    )
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        verbose=False,
    )
    return chain


# 벡터스토어 및 체인 초기화
if os.path.exists(FAISS_INDEX_PATH):
    vectorstore = load_vectorstore()
else:
    vectorstore = build_vectorstore()

chain = build_chain(vectorstore)
print("RAG 준비 완료.\n")


def chat(message, history):
    result = chain.invoke({"question": message})
    answer = result["answer"]

    sources = result.get("source_documents", [])
    if sources:
        pages = sorted({int(doc.metadata.get("page", 0)) + 1 for doc in sources})
        answer += f"\n\n📄 참고 페이지: {pages}"

    return answer


demo = gr.ChatInterface(
    fn=chat,
    title="file1.pdf RAG 챗봇",
    description="file1.pdf 문서를 기반으로 질문에 답변합니다. 이전 대화 문맥을 유지합니다.",
    examples=["이 문서의 주요 내용은 무엇인가요?"],
)

if __name__ == "__main__":
    demo.launch()
