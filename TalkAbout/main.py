import requests
from datetime import date, timedelta
from bs4 import BeautifulSoup
from konlpy.tag import Okt
#from pymongo import MongoClient
import pymysql
from matplotlib import pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
from gensim.models.word2vec import Word2Vec

##mySql 접속 설정

conn = pymysql.connect(host='localhost', user='root', password='1234', db='talkabout_db', charset='utf8')
##수집날짜
today = date.today()
tomorrow = date.today() + timedelta(1)
#today = date.today()
#tomorrow = date.today() + timedelta(1)
current_time = today.strftime('%Y%m%d')
tmr_time = tomorrow.strftime('%Y%m%d')
print("조회 날짜 : ", current_time, "내일 날짜 : ", tmr_time)
##크롤링 수집대상 url
webPage = requests.get("https://news.naver.com/main/ranking/popularDay.nhn?rankingType=popular_day&sectionId=102&date=" + current_time)
soup = BeautifulSoup(webPage.content, "html.parser")

##형태소 분석 객체 생성
okt = Okt()

lstHead = [] # 형태소 분석 결과 리스트
lst_word2vec = [] # 형태소 분석 결과 리스트

##형태소 분석 수행
for cnt in range (0,len(soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})),2):
    ##print("href  :: " + soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('href'))
    ##str = soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('title')
    ##print(soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('title'))
    ##분석 결과 리스트에 키워드(class명:'nclicks(rnk.soc)')와 url 주소 삽입
    lstHead.append(okt.pos(soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('title'))+[soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('title')]+[soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('href')])
    lst_word2vec.append(okt.nouns(soup.find_all(attrs={'class': 'nclicks(rnk.soc)'})[cnt].get('title')))
    #print(lstHead[cnt//2])
    #print(lst_word2vec[cnt//2])
print(lst_word2vec)
#print(lstHead)

##DB sql수행 객체
curs = conn.cursor()

## 형태소 분석 중 명사 뽑기
for i in range (len(lstHead)):
    for j in lstHead[i][:-2]:
        if j[1] != 'Noun' or len(j[0]) <= 1: # 명사와 한글자 길이(의미없는 문자)의 문자 제거
            lstHead[i].remove(j)

## 단어 임베딩 중 명사 한자리 글자 빼기
for i in range(len(lst_word2vec)):
    for j in lst_word2vec[i]:
        if len(j) <= 1:  # 명사와 한글자 길이(의미없는 문자)의 문자 제거
            lst_word2vec[i].remove(j)


##DB에 형태소 분석 결과 반영
for i in range(len(lstHead)):
    for j in lstHead[i][:-2]:
        keyword = j[0]
        title = lstHead[i][-2]
        url = lstHead[i][-1]
        sql = "insert into tb_keyword (keyword, title, keyword_url, kw_date) values (%s, %s, %s, %s)"
        curs.execute(sql, (keyword,title,url,current_time))
        conn.commit()

##select keword, title, count(keword) from tb_keword group by keword  order by 2 desc;
##select keword, count(keword) from tb_keword group by keword  order by 2 desc;
##수집결과 파이그래프 작성
curs = conn.cursor()
sql = "select keyword, count(keyword) from tb_keyword where kw_date >= "+current_time+" and kw_date < "+tmr_time+" group by keyword order by 2 desc"
curs.execute(sql)

data = curs.fetchall()

resData = []
resCatagories = []
for i in range(5) :
    resData.append(data[i][1]) # 데이터 집합
    resCatagories.append(data[i][0]) # 컬럼명 집합

##파이 그래프 폰트설정 및 그리기
font_location = 'C:\Windows\Fonts\LG PC.ttf'
font_name = fm.FontProperties(fname = font_location).get_name()
plt.rc('font',family=font_name)
plt.pie(resData, labels=resCatagories, autopct='%0.1f%%')
plt.show()


print("::::::::::고유 명사 LIST & 기사 제목 & URL::::::::::")
#print(lstHead)
#print(lst_word2vec)

## 중심 키워드가 포함된 연관 기사 검색
res_word2vec = [] # 뉴스기사 리스트 중 연관 단어 리스트
for i in range(len(lst_word2vec)): # 2차원 리스트 중 행 읽기
    if resCatagories[0] in lst_word2vec[i]: # 중심단어가 포함 된 경우
        res_word2vec.append(lst_word2vec[i]) # 중심단어가 포함 된 리스트 append
#print(res_word2vec)

model = Word2Vec(res_word2vec, sg=1,    # 0: CBOW, 1:Skip-Gram
                 size=100,              # 벡터크기
                 window=5,              # 고려할 앞뒤 폭
                 min_count=2,           # 사용할 단어의 최소 빈도
                 workers=8 )            # 동시에 사용할 작업(코어) 수
model.init_sims(replace=True)           # 필요없는 메모리 unload
print("핫 키워드 >> ",resCatagories[0], ", 핫 키워드 등장 수 >> ",resData[0])
## 판다스 표작성
df = pd.DataFrame(model.wv.most_similar(resCatagories[0], topn=10), columns=['단어','유사도'])
#df.head(3)
print(df)

req_kwdRank = model.wv.most_similar(resCatagories[0], topn=10) # 연관도 분석 리스트 결과 전달

##DB sql수행 객체
curs = conn.cursor()

for i in range(len(req_kwdRank)): # 분석 결과 리스트 행별로 반복
    sql = "insert into tb_relt_kwrd (relt_kwrd, cnt_kwrd, daily, kw_rank, kw_date) values (%s, %s, %s, %s, %s)"
    curs.execute(sql, (req_kwdRank[i][0], resCatagories[0], 1, i, current_time))
    conn.commit()

conn.close()

'''
##몽고디비 설정
client = MongoClient('localhost', 27017)
db = client["talkabout_db"]
##collection = db["tb_keword"]
coll = db.tb_keword
##coll_list = db.list_collection_names()

##print(coll_list)
print(coll.find_one())
'''