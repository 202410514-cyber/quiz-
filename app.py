import os
from flask import Flask, request, redirect, url_for, render_template_string, session, send_from_directory, jsonify
import random
import time

app = Flask(__name__)
app.secret_key = "semodan-secret-key-gamified"

# ---------------- 데이터 ----------------
user_words = {}     # 사용자별 단어장

# ---------------- HTML TEMPLATES ----------------
BASE_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>세상의 모든 단어</title>
    <link rel="stylesheet" href="styles.css">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <header>✨ 세상의 모든 단어</header>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

LOGIN_HTML = """
{% extends "base" %}
{% block content %}
<div class="card" style="max-width: 400px; margin: 50px auto;">
    <h2>🔑 로그인</h2>
    <form method="post" action="/login">
        <input name="user" placeholder="멋진 닉네임을 입력하세요" required autofocus>
        <button type="submit">시작하기</button>
    </form>
</div>
{% endblock %}
"""

HOME_HTML = """
{% extends "base" %}
{% block content %}
<div class="card top-bar">
    <div style="font-size: 20px;"><b>👋 환영합니다, {{ user }}님!</b></div>
    <a href="/logout" class="logout-link">로그아웃</a>
</div>

<!-- 상단 풀 위드 배너: 게임 진입점 -->
<div class="card" style="text-align: center; padding: 40px 20px; background: linear-gradient(135deg, rgba(99,102,241,0.2) 0%, rgba(244,63,94,0.2) 100%);">
    <h2 style="justify-content: center; font-size: 32px; margin-bottom: 5px;">🎮 60초 타임어택 모드</h2>
    <p style="color: var(--text-muted); margin-bottom: 25px;">단어를 보고 빠르게 뜻을 맞춰보세요! 시간이 끝나기 전에 최대한 스코어를 올려보세요.</p>
    {% if words|length > 0 %}
        <form action="/start_quiz" method="post" style="max-width: 350px; margin: 0 auto;">
            <button type="submit" class="accent-btn">🔥 게임 시작하기</button>
        </form>
    {% else %}
        <p style="color: var(--accent); font-weight: bold;">[!] 퀴즈를 시작하려면 아래에서 단어를 한 개 이상 추가해 주세요.</p>
    {% endif %}
</div>

<div class="row">

    <!-- 단어 추가 폼 (왼쪽) -->
    <div class="col" style="flex: 1;">
        <div class="card">
            <h2>➕ 단어 추가</h2>
            <form method="post" action="/add">
                <input name="category" placeholder="카테고리명 (예: 토익, 일상)" required autocomplete="off">
                <input name="en" placeholder="단어" required autocomplete="off">
                <input name="ko" placeholder="뜻 (한글)" required autocomplete="off">
                <button type="submit" style="background: var(--primary);">단어장 목록에 추가</button>
            </form>
        </div>
    </div>

    <!-- 단어장 관리 리스트 (오른쪽) -->
    <div class="col" style="flex: 2;">
        <div class="card">
            <h2>📚 내 단어장 관리</h2>
            <div class="word-list">
                {% for group in words|groupby('cat') %}
                <details open>
                    <summary>📁 {{ group.grouper }} ({{ group.list|length }}개)</summary>
                    <div style="margin-top: 15px;">
                    {% for w in group.list %}
                        <div class="word-row">
                            <span class="word-en">{{ w.en }}</span> 
                            <span class="word-ko">{{ w.ko }}</span>
                        </div>
                    {% endfor %}
                    </div>
                </details>
                {% else %}
                <div style="text-align:center; padding: 40px; color: var(--text-muted);">
                    아직 단어가 등록되지 않았습니다.<br>좌측 폼을 이용해 첫 단어를 입력해주세요!
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
</div>
{% endblock %}
"""

QUIZ_HTML = """
{% extends "base" %}
{% block content %}
<div class="card" style="max-width: 600px; margin: 0 auto; text-align: center; position: relative;">
    
    <div class="top-bar" style="margin-bottom: 20px;">
        <div>
            <span style="font-size: 18px; color: var(--text-muted);">현재 점수</span>
            <span style="font-size: 24px; font-weight: 800; color: #10b981; margin-left: 10px;" id="live-score">{{ score }} 점</span>
        </div>
        <a href="/quiz_result" class="logout-link" style="color: #f43f5e; background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.2);">🛑 그만하기</a>
    </div>

    <div class="timer-container">
        <div class="timer-circle" id="timer-circle">
            <div class="timer-pulse" id="timer-pulse"></div>
            <span id="time-display">{{ time_left }}</span>
        </div>
    </div>
    
    <p style="color: var(--text-muted);">이 단어의 뜻은 무엇일까요?</p>
    <div class="quiz-word">{{ word_en }}</div>
    
    <form id="quiz-form">
        <input type="text" id="answer-input" name="answer" placeholder="정답을 입력하세요" autofocus autocomplete="off" style="text-align: center; font-size: 20px; padding: 20px;">
    </form>

    <form id="end-form" action="/quiz_result" method="get" style="display:none;"></form>
</div>

<!-- 피드백 애니메이션 오버레이 -->
<div id="feedback" class="feedback-overlay">
    <div id="feedback-text" class="feedback-text"></div>
</div>

<script>
    let timeLeft = parseInt("{{ time_left }}");
    const timeDisplay = document.getElementById('time-display');
    const timerCircle = document.getElementById('timer-circle');
    const timerPulse = document.getElementById('timer-pulse');
    const endForm = document.getElementById('end-form');
    let gameActive = true;

    // 카운트다운 로직
    const countdown = setInterval(() => {
        timeLeft--;
        if(timeLeft >= 0) timeDisplay.innerText = timeLeft;
        
        if (timeLeft <= 10 && timeLeft > 0) {
            timerCircle.style.color = '#f43f5e';
            timerCircle.style.borderColor = '#f43f5e';
            timerPulse.style.borderColor = '#f43f5e';
        }
        
        if (timeLeft <= 0) {
            clearInterval(countdown);
            gameActive = false;
            endForm.submit(); // 시간 종료 시 결과 페이지로
        }
    }, 1000);

    // 폼 제출 (AJAX 통신으로 새로고침 없이 즉각 피드백)
    const form = document.getElementById('quiz-form');
    const input = document.getElementById('answer-input');
    const liveScore = document.getElementById('live-score');
    const feedback = document.getElementById('feedback');
    const feedbackText = document.getElementById('feedback-text');

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        if(!gameActive) return;

        const answer = input.value.trim();
        if(!answer) return;
        
        input.value = ''; // 다음 문제를 위해 입력창 즉시 비우기

        fetch('/submit_answer', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'answer=' + encodeURIComponent(answer)
        })
        .then(res => res.json())
        .then(data => {
            if(data.status === 'timeout') {
                endForm.submit();
                return;
            }
            
            // 정답/오답 애니메이션 효과
            if(data.correct) {
                feedbackText.innerText = "⭕ 정답!";
                feedbackText.style.color = "#10b981";
                feedbackText.style.textShadow = "0 0 20px rgba(16, 185, 129, 0.5)";
            } else {
                feedbackText.innerHTML = "❌ 오답<br><span style='font-size:30px; color:#fff;'>정답: " + data.actual_ko + "</span>";
                feedbackText.style.color = "#f43f5e";
                feedbackText.style.textShadow = "0 0 20px rgba(244, 63, 94, 0.5)";
            }
            
            feedback.classList.add('show');
            setTimeout(() => feedback.classList.remove('show'), 600);

            // 점수 갱신 및 다음 단어 출제
            liveScore.innerText = data.new_score + " 점";
            document.querySelector('.quiz-word').innerText = data.next_word_en;
        });
    });
</script>
{% endblock %}
"""

RESULT_HTML = """
{% extends "base" %}
{% block content %}
<div class="card" style="max-width: 500px; margin: 50px auto; text-align: center;">
    <h2 style="justify-content: center; font-size: 36px; margin-bottom: 10px;">⏰ 타임오버!</h2>
    <p style="color: var(--text-muted); margin-bottom: 30px;">수고하셨습니다. 게임이 종료되었습니다!</p>
    
    <div style="background: rgba(0,0,0,0.3); border-radius: 20px; padding: 40px; margin-bottom: 30px; border: 1px solid var(--card-border);">
        <div style="font-size: 18px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 2px;">당신의 최종 점수</div>
        <div style="font-size: 72px; font-weight: 900; color: #fff; text-shadow: 0 0 20px rgba(99,102,241,0.5);">{{ score }}</div>
    </div>
    
    <a href="/" style="display:block; text-decoration:none;">
        <button style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);">메인으로 돌아가기</button>
    </a>
</div>
{% endblock %}
"""

def render(template, **kwargs):
    # 간단한 템플릿 엔진 로직 (base HTML 레이아웃 주입)
    content = template.replace('{% extends "base" %}\n{% block content %}', '').replace('{% endblock %}', '')
    final_html = BASE_HTML.replace('{% block content %}{% endblock %}', content)
    return render_template_string(final_html, **kwargs)

@app.route("/styles.css")
def styles():
    return send_from_directory(".", "styles.css")

@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return render(LOGIN_HTML)
        
    user_words.setdefault(user, [])
    for w in user_words[user]:
        if "cat" not in w:
            w["cat"] = "기본"
            
    return render(HOME_HTML, user=user, words=user_words[user])

@app.route("/login", methods=["POST"])
def login():
    session["user"] = request.form["user"]
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/add", methods=["POST"])
def add():
    user = session.get("user")
    if not user: return redirect(url_for("home"))
    
    user_words.setdefault(user, []).append({
        "cat": request.form.get("category", "기본"),
        "en": request.form["en"],
        "ko": request.form["ko"]
    })
    return redirect(url_for("home"))

@app.route("/start_quiz", methods=["POST"])
def start_quiz():
    user = session.get("user")
    if not user or not user_words.get(user):
        return redirect(url_for("home"))
        
    # 게임 셋팅: 60초 게임 타이머 및 점수 초기화
    session['quiz_end_time'] = time.time() + 60
    session['game_score'] = 0
    
    # 첫 단어 픽
    first_word = random.choice(user_words[user])
    session['current_word_en'] = first_word['en']
    session['current_word_ko'] = first_word['ko']
    
    return redirect(url_for("play_quiz"))

@app.route("/play_quiz")
def play_quiz():
    user = session.get("user")
    if not user: return redirect(url_for("home"))
    
    end_time = session.get('quiz_end_time', 0)
    time_left = int(end_time - time.time())
    
    if time_left <= 0:
        return redirect(url_for("quiz_result"))
        
    return render(QUIZ_HTML, 
                 score=session.get('game_score', 0),
                 time_left=time_left,
                 word_en=session.get('current_word_en', ''))

@app.route("/submit_answer", methods=["POST"])
def submit_answer():
    user = session.get("user")
    if not user: return jsonify({'status': 'error'})
    
    end_time = session.get('quiz_end_time', 0)
    if time.time() > end_time:
        return jsonify({'status': 'timeout'})
        
    answer = request.form.get("answer", "").strip()
    correct_ans = session.get('current_word_ko', '')
    
    is_correct = (answer == correct_ans)
    
    if is_correct:
        session['game_score'] = session.get('game_score', 0) + 10
        
    # 다음 단어를 위해 랜덤 추출
    next_word = random.choice(user_words[user])
    session['current_word_en'] = next_word['en']
    session['current_word_ko'] = next_word['ko']
    
    return jsonify({
        'status': 'ok',
        'correct': is_correct,
        'actual_ko': correct_ans,
        'new_score': session['game_score'],
        'next_word_en': next_word['en']
    })

@app.route("/quiz_result")
def quiz_result():
    user = session.get("user")
    if not user: return redirect(url_for("home"))
    
    final_score = session.get('game_score', 0)
    return render(RESULT_HTML, score=final_score)

if __name__ == "__main__":
    app.run(debug=True)
