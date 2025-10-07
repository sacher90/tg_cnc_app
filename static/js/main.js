/* global Telegram */
(function () {
    const steps = [1, 2, 3, 4, 5];
    let currentStep = 1;
    const state = {
        userId: null,
        toolType: null,
        materialName: '',
        toolMaterial: null,
        diameter: null,
        teeth: null,
        materialProperties: null,
    };

    const stepElements = new Map();
    steps.forEach(step => {
        stepElements.set(step, document.getElementById(`step-${step}`));
    });

    const backBtn = document.getElementById('backBtn');
    const nextBtn = document.getElementById('nextBtn');
    const resetBtn = document.getElementById('resetBtn');
    const errorBox = document.getElementById('errorBox');
    const accessMessage = document.getElementById('accessMessage');
    const materialInput = document.getElementById('materialInput');
    const diameterInput = document.getElementById('diameterInput');
    const teethInput = document.getElementById('teethInput');
    const resultsContainer = document.getElementById('resultsContainer');
    const recommendationsContainer = document.getElementById('recommendationsContainer');

    const toolButtons = document.querySelectorAll('.tool-btn');
    const toolMaterialButtons = document.querySelectorAll('.tool-material-btn');

    toolButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            state.toolType = btn.dataset.tool;
            highlightSelection(toolButtons, btn);
            maybeNext();
        });
    });

    toolMaterialButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            state.toolMaterial = btn.dataset.material;
            highlightSelection(toolMaterialButtons, btn);
            maybeNext();
        });
    });

    backBtn.addEventListener('click', () => {
        if (currentStep > 1) {
            setStep(currentStep - 1);
        }
    });

    resetBtn.addEventListener('click', resetFlow);

    nextBtn.addEventListener('click', async () => {
        clearError();
        switch (currentStep) {
            case 1:
                if (!state.toolType) return showError('Выберите тип инструмента.');
                setStep(2);
                break;
            case 2:
                state.materialName = (materialInput.value || '').trim();
                if (!state.materialName) return showError('Введите материал заготовки.');
                setStep(3);
                break;
            case 3:
                if (!state.toolMaterial) return showError('Выберите материал инструмента.');
                setStep(4);
                break;
            case 4:
                const diameterVal = parseFloat(diameterInput.value);
                const teethVal = parseInt(teethInput.value, 10);
                if (Number.isNaN(diameterVal) || diameterVal <= 0) {
                    return showError('Укажите диаметр инструмента.');
                }
                if (Number.isNaN(teethVal) || teethVal <= 0) {
                    return showError('Введите количество зубьев.');
                }
                state.diameter = diameterVal;
                state.teeth = teethVal;
                await fetchResults();
                setStep(5);
                break;
            default:
                break;
        }
    });

    function highlightSelection(nodeList, active) {
        nodeList.forEach(btn => btn.classList.remove('active'));
        active.classList.add('active');
    }

    function setStep(step) {
        currentStep = step;
        steps.forEach(idx => {
            const el = stepElements.get(idx);
            if (!el) return;
            el.classList.toggle('active', idx === step);
        });
        backBtn.disabled = currentStep === 1;
        nextBtn.textContent = currentStep === 5 ? 'Готово' : 'Далее';
        if (currentStep === 5) {
            nextBtn.disabled = true;
        } else {
            nextBtn.disabled = false;
        }
    }

    function resetFlow() {
        state.toolType = null;
        state.materialName = '';
        state.toolMaterial = null;
        state.diameter = null;
        state.teeth = null;
        state.materialProperties = null;
        toolButtons.forEach(btn => btn.classList.remove('active'));
        toolMaterialButtons.forEach(btn => btn.classList.remove('active'));
        materialInput.value = '';
        diameterInput.value = '';
        teethInput.value = '';
        resultsContainer.innerHTML = '';
        recommendationsContainer.innerHTML = '';
        nextBtn.disabled = false;
        setStep(1);
    }

    function maybeNext() {
        if ((currentStep === 1 && state.toolType) || (currentStep === 3 && state.toolMaterial)) {
            // highlight enables but no auto step
        }
    }

    function showError(message) {
        errorBox.style.display = 'block';
        errorBox.textContent = message;
    }

    function clearError() {
        errorBox.style.display = 'none';
        errorBox.textContent = '';
    }

    async function determineUser() {
        let userId = initialUserId || null;
        try {
            if (window.Telegram && Telegram.WebApp) {
                Telegram.WebApp.ready();
                const tgUser = Telegram.WebApp.initDataUnsafe?.user;
                if (tgUser?.id) {
                    userId = tgUser.id;
                }
            }
        } catch (err) {
            console.warn('Telegram SDK unavailable', err);
        }
        if (!userId) {
            userId = sessionStorage.getItem('demoUserId');
            if (!userId) {
                userId = prompt('Введите demo Telegram ID для теста', '123456');
                if (userId) {
                    sessionStorage.setItem('demoUserId', userId);
                }
            }
        }
        state.userId = userId;
        if (!userId) {
            showError('Не удалось определить пользователя.');
            nextBtn.disabled = true;
            return;
        }
        await checkAccess(userId);
    }

    async function checkAccess(userId) {
        const res = await fetch('/api/check_access', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await res.json();
        if (!res.ok || !data.allowed) {
            accessMessage.textContent = data.message || 'Доступ запрещён';
            nextBtn.disabled = true;
            backBtn.disabled = true;
            resetBtn.disabled = true;
        } else {
            accessMessage.textContent = '✅ Авторизация успешна';
            setStep(1);
        }
    }

    async function fetchMaterials() {
        const res = await fetch('/api/materials');
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('materialsList');
        list.innerHTML = '';
        (data.materials || []).forEach(material => {
            const option = document.createElement('option');
            option.value = material.name;
            list.appendChild(option);
        });
    }

    async function fetchResults() {
        if (!state.userId) {
            showError('Нет данных пользователя');
            return;
        }
        try {
            const analyzeRes = await fetch('/api/materials/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: state.userId,
                    material: state.materialName
                })
            });
            const analyzeData = await analyzeRes.json();
            if (!analyzeRes.ok) {
                showError(analyzeData.error || 'Ошибка анализа материала');
                return;
            }
            state.materialProperties = analyzeData.material;

            const calcRes = await fetch('/api/calc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: state.userId,
                    tool_type: state.toolType,
                    tool_material: state.toolMaterial,
                    diameter: state.diameter,
                    teeth: state.teeth,
                    material_properties: state.materialProperties
                })
            });
            const calcData = await calcRes.json();
            if (!calcRes.ok) {
                showError(calcData.error || 'Ошибка расчёта режимов');
                return;
            }
            renderResults(calcData.calculation, calcData.recommendations);
        } catch (err) {
            console.error(err);
            showError('Не удалось выполнить расчёт.');
        }
    }

    function renderResults(calc, recommendations) {
        resultsContainer.innerHTML = `
            <table>
                <tr><th>Vc, м/мин</th><td>${calc.vc}</td></tr>
                <tr><th>n, об/мин</th><td>${calc.n}</td></tr>
                <tr><th>fz, мм/зуб</th><td>${calc.fz}</td></tr>
                <tr><th>F, мм/мин</th><td>${calc.feed}</td></tr>
                <tr><th>ap, мм</th><td>${calc.ap}</td></tr>
                <tr><th>ae, мм</th><td>${calc.ae}</td></tr>
            </table>
        `;
        const riskBadges = (recommendations.risks || []).map(r => `<span class="pill">⚠️ ${r}</span>`).join(' ');
        const notesList = (recommendations.notes || []).map(n => `<li>💡 ${n}</li>`).join('');
        recommendationsContainer.innerHTML = `
            <div><strong>⚠️ Риски:</strong><br>${riskBadges || '—'}</div>
            <div style="margin-top:12px;"><strong>💡 Рекомендации:</strong><ul>${notesList || '<li>—</li>'}</ul></div>
            <div style="margin-top:12px;">СОЖ: ${recommendations.coolant || 'по справочнику'}</div>
            <div style="margin-top:4px;">Температурный риск: ${recommendations.temperature_risk || '—'}, наклёп: ${recommendations.work_hardening || '—'}</div>
        `;
    }

    document.addEventListener('DOMContentLoaded', () => {
        setStep(1);
        determineUser();
        fetchMaterials();
    });
})();
