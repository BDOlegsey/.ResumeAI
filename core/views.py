from django.shortcuts import render, redirect
from django.http import HttpResponse

def index(request):
    if request.method == "POST":
        employers = request.POST.get("employers", "").strip()
        achievements = request.POST.get("achievements", "").strip()

        # Сохраняем в сессию
        request.session["employers"] = employers
        request.session["achievements"] = achievements

        # === 🚀 СЮДА ПОЗЖЕ ВСТАВИТЬ ВЫЗОВ LLM-АГЕНТА ===
        # Пример будущего кода:
        # resume_text = your_llm_agent.generate_resume(employers, achievements)
        #
        # А пока — заглушка:
        if employers or achievements:
            resume_text = (
                "📄 Ваше резюме (заглушка — ИИ пока не подключён)\n\n"
                "💼 Работодатели:\n" + (employers if employers else "—") + "\n\n"
                "🏆 Достижения:\n" + (achievements if achievements else "—") + "\n\n"
                "✅ Совет: в будущем здесь будет профессионально составленное резюме от LLM-агента."
            )
        else:
            resume_text = "⚠️ Вы не ввели ни работодателей, ни достижений. Вернитесь и заполните хотя бы одно поле."

        # Сохраняем результат в сессию
        request.session["generated_resume"] = resume_text

        # Перенаправляем на страницу с результатом
        return redirect("result")

    # GET-запрос: показываем форму с сохранёнными данными (если есть)
    employers = request.session.get("employers", "")
    achievements = request.session.get("achievements", "")
    return render(request, "index.html", {
        "employers": employers,
        "achievements": achievements
    })

def result(request):
    # Получаем сгенерированное резюме из сессии
    resume = request.session.get("generated_resume", "Резюме не найдено. Вернитесь на главную и создайте его.")
    return render(request, "result.html", {"resume": resume})

def help_page(request):
    return render(request, "help.html")

def contacts(request):
    return render(request, "contacts.html")

def how_it_works(request):
    return render(request, "how_it_works.html")

def about(request):
    return render(request, "about.html")