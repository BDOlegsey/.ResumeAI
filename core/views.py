from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm

def index(request):
    if request.method == "POST":
        # Проверяем, авторизован ли пользователь
        if not request.user.is_authenticated:
            messages.warning(request, "Для создания резюме необходимо войти в систему.")
            return redirect('login')

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
                                                                              "🏆 Достижения:\n" + (
                        achievements if achievements else "—") + "\n\n"
                                                                 f"👤 Создано пользователем: {request.user.username}\n\n"
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


@login_required
def result(request):
    # Получаем сгенерированное резюме из сессии
    resume = request.session.get("generated_resume", "Резюме не найдено. Вернитесь на главную и создайте его.")
    return render(request, "result.html", {"resume": resume})


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}! Вы успешно зарегистрировались.')
            return redirect('index')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {username}!')
                next_url = request.GET.get('next', 'index')
                return redirect(next_url)
    else:
        form = CustomAuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('index')


def help_page(request):
    return render(request, "help.html")


def contacts(request):
    return render(request, "contacts.html")


def how_it_works(request):
    return render(request, "how_it_works.html")


def about(request):
    return render(request, "about.html")