document.addEventListener('DOMContentLoaded', () => {
    hydrateVehicleFields();
    handleAvariaRepeater();
    markActiveNav();
    setupSidenav();
    setupToasts();
    setupPasswordToggles();
    setupChecklistStatus();
    setupFuelSlider();
    setupFormSubmission();
    setupFuelLevelsAutoRefresh();
});

function setupSidenav() {
    const toggle = document.querySelector('[data-sidenav-toggle]');
    const sidenav = document.getElementById('appSidenav');
    const overlay = document.querySelector('[data-sidenav-overlay]');
    const closeBtn = document.querySelector('[data-sidenav-close]');

    if (!toggle || !sidenav || !overlay) return;

    const open = () => {
        sidenav.classList.add('is-open');
        overlay.classList.add('is-visible');
        toggle.setAttribute('aria-expanded', 'true');
        sidenav.setAttribute('aria-hidden', 'false');
        document.body.classList.add('sidenav-open');
    };

    const close = () => {
        sidenav.classList.remove('is-open');
        overlay.classList.remove('is-visible');
        toggle.setAttribute('aria-expanded', 'false');
        sidenav.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('sidenav-open');
    };

    toggle.addEventListener('click', () => {
        const isOpen = sidenav.classList.contains('is-open');
        if (isOpen) {
            close();
        } else {
            open();
        }
    });

    overlay.addEventListener('click', close);

    if (closeBtn) {
        closeBtn.addEventListener('click', close);
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && sidenav.classList.contains('is-open')) {
            close();
        }
    });
}

function setupToasts() {
    const stack = document.querySelector('[data-toast-stack]');
    if (!stack) return;

    const removeToast = (toast) => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    };

    stack.querySelectorAll('.toast').forEach((toast) => {
        const close = toast.querySelector('.toast-close');
        if (close) {
            close.addEventListener('click', () => removeToast(toast));
        }
        setTimeout(() => removeToast(toast), 6000);
    });
}

// Create and show a toast programmatically
function showToast(message, type = 'info') {
    const stack = document.querySelector('[data-toast-stack]');
    if (!stack) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const msg = document.createElement('div');
    msg.className = 'toast-message';
    msg.textContent = message;

    const close = document.createElement('button');
    close.className = 'toast-close';
    close.setAttribute('type', 'button');
    close.innerHTML = '&times;';
    close.addEventListener('click', () => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    });

    toast.appendChild(msg);
    toast.appendChild(close);
    stack.appendChild(toast);

    // Auto remove after 5s
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 200);
        }
    }, 5000);
}

// Setup menu actions (show 'em breve' toast for items marked soon)
function setupSidenavMenuActions() {
    const sidenav = document.getElementById('appSidenav');
    if (!sidenav) return;

    sidenav.addEventListener('click', (evt) => {
        const target = evt.target.closest('[data-menu-action]');
        if (!target) return;
        const action = target.getAttribute('data-menu-action');
        if (action === 'soon') {
            evt.preventDefault();
            showToast('em breve', 'info');
            // close sidenav if open
            const overlay = document.querySelector('[data-sidenav-overlay]');
            const toggle = document.querySelector('[data-sidenav-toggle]');
            if (overlay) overlay.classList.remove('is-visible');
            sidenav.classList.remove('is-open');
            document.body.classList.remove('sidenav-open');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
            sidenav.setAttribute('aria-hidden', 'true');
        }
    });
}

// Initialize additional handlers after DOM ready
document.addEventListener('DOMContentLoaded', () => {
    setupSidenavMenuActions();
    // expose showToast globally if need be
    window.showToast = showToast;
});

function hydrateVehicleFields() {
    const select = document.getElementById('veiculoSelect');
    if (!select) return;
    const modelo = document.getElementById('fieldModelo');
    const placa = document.getElementById('fieldPlaca');
    const marca = document.getElementById('fieldMarca');
    const tipo = document.getElementById('fieldTipo');

    select.addEventListener('change', () => {
        const option = select.options[select.selectedIndex];
        if (!option || !option.dataset) return;
        modelo.value = option.dataset.modelo || '';
        placa.value = option.dataset.placa || '';
        marca.value = option.dataset.marca || '';
        tipo.value = option.dataset.tipo || '';
    });
}

function handleAvariaRepeater() {
    const btn = document.getElementById('btnAddAvaria');
    const list = document.getElementById('avariaList');
    if (!btn || !list) return;

    btn.addEventListener('click', () => {
        const template = list.querySelector('.avaria-item');
        if (!template) return;
        const clone = template.cloneNode(true);
        clone.querySelectorAll('input').forEach(input => {
            input.value = '';
        });
        list.appendChild(clone);
    });
}

function markActiveNav() {
    const current = window.location.pathname;
    document.querySelectorAll('.app-nav .nav-link').forEach(link => {
        if (link.getAttribute('href') === current) {
            link.classList.add('active');
        }
    });
}

function setupPasswordToggles() {
    document.querySelectorAll('.toggle-password').forEach(button => {
        const targetId = button.dataset.target;
        const input = document.getElementById(targetId);
        if (!input) return;

        button.addEventListener('click', () => {
            const isPassword = input.getAttribute('type') === 'password';
            input.setAttribute('type', isPassword ? 'text' : 'password');
            button.classList.toggle('is-active', !isPassword);
        });
    });
}

function setupChecklistStatus() {
    const selects = document.querySelectorAll('[data-status-select]');
    const avariaSection = document.getElementById('avariaSection');

    if (!selects.length) {
        if (avariaSection) {
            avariaSection.hidden = false;
        }
        return;
    }

    const refreshAvariaSection = () => {
        if (!avariaSection) return;
        const hasNC = Array.from(selects).some(select => select.value === 'NC');
        avariaSection.hidden = !hasNC;
    };

    selects.forEach(select => {
        const row = select.closest('[data-status-row]');
        const observation = row ? row.querySelector('[data-status-obs]') : null;

        const applyState = () => {
            const value = select.value;
            select.classList.remove('status-ok', 'status-alert');
            if (value === 'C') {
                select.classList.add('status-ok');
            } else if (value === 'NC') {
                select.classList.add('status-alert');
            }

            if (observation) {
                const shouldShow = value === 'NC';
                observation.hidden = !shouldShow;
                if (!shouldShow) {
                    observation.querySelectorAll('input, textarea').forEach(field => {
                        field.value = '';
                    });
                }
            }

            refreshAvariaSection();
        };

        select.addEventListener('change', applyState);
        applyState();
    });

    refreshAvariaSection();
}

function setupFuelSlider() {
    document.querySelectorAll('[data-fuel-control]').forEach(control => {
        const slider = control.querySelector('[data-fuel-slider]');
        const hidden = control.querySelector('[data-fuel-value]');
        const labels = Array.from(control.querySelectorAll('[data-fuel-label]'));
        if (!slider || !hidden || !labels.length) return;

        const clampIndex = value => {
            const maxIndex = labels.length - 1;
            if (Number.isNaN(value)) return 0;
            return Math.min(Math.max(value, 0), maxIndex);
        };

        const update = () => {
            const index = clampIndex(parseInt(slider.value, 10));
            const label = labels[index];
            const selected = (label && label.dataset.value) || '';
            hidden.value = selected;
            slider.setAttribute('aria-valuetext', selected);
            labels.forEach((item, idx) => item.classList.toggle('is-active', idx === index));
        };

        slider.addEventListener('input', update);
        slider.addEventListener('change', update);
        update();
    });
}

function setupFormSubmission() {
    const forms = document.querySelectorAll('form.report-form');
    forms.forEach(form => {
        form.addEventListener('submit', (evt) => {
            const veiculo = form.querySelector('select[name="veiculo_id"]');
            const dataSaida = form.querySelector('input[name="data_hora_saida"]');
            const dataChegada = form.querySelector('input[name="data_hora_chegada"]');
            const kmInicial = form.querySelector('input[name="km_inicial"]');
            const kmFinal = form.querySelector('input[name="km_final"]');
            const combustivel = form.querySelector('input[name="combustivel_saida"]') || form.querySelector('input[name="combustivel_chegada"]');
            
            // Se o formulário não possui campos de viagem (partida/chegada),
            // não executa as validações específicas de relatório.
            const hasTripFields = dataSaida || dataChegada || kmInicial || kmFinal || form.querySelector('[data-fuel-control]');
            if (!hasTripFields) {
                return; // permite envio normal (ex: formulário de avarias)
            }

            const isArrival = !!dataChegada;

            // Only validate vehicle for departure forms
            if (!isArrival && veiculo && !veiculo.value) {
                evt.preventDefault();
                alert('Por favor, selecione um veículo.');
                return;
            }

            if (isArrival) {
                if (!dataChegada || !dataChegada.value) {
                    evt.preventDefault();
                    alert('Por favor, informe a data de chegada.');
                    return;
                }
                if (!kmFinal || !kmFinal.value) {
                    evt.preventDefault();
                    alert('Por favor, informe o KM final.');
                    return;
                }
            } else {
                if (!dataSaida || !dataSaida.value) {
                    evt.preventDefault();
                    alert('Por favor, informe a data e horário de saída.');
                    return;
                }
                if (!kmInicial || !kmInicial.value) {
                    evt.preventDefault();
                    alert('Por favor, informe o KM inicial.');
                    return;
                }
            }

            if (!combustivel || !combustivel.value) {
                evt.preventDefault();
                alert('Por favor, defina o nível de combustível.');
                return;
            }
        });
    });
}

function setupFuelLevelsAutoRefresh() {
    const grid = document.querySelector('[data-fuel-grid]');
    if (!grid) return;

    const escapeHtml = (value) => {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    const renderCards = (items, brasiliaNowFromApi, authenticated) => {
        const fragment = document.createDocumentFragment();
        items.forEach((item) => {
            const card = document.createElement('article');
            const criticalClass = item.is_critical_focus ? ' fuel-card--low' : '';
            card.className = `fuel-card fuel-card--${escapeHtml(item.nivel_status || 'unknown')}${criticalClass}`;

            const onlineClass = item.status_online ? 'online' : 'offline';
            const nivelPercent = item.nivel_percent ?? 0;
            const nivelDisplay = item.nivel_display || '—';
            const autonomia = item.autonomia_display || '—';
            const updated = item.ultima_atualizacao_display || 'indisponível';
            const brNow = item.brasilia_now_display || brasiliaNowFromApi || '—';
            const diff = item.ultima_diff_display || '—';
            const local = item.local || item.nome || 'Gerador';
            const fuelColor = item.level_color || '#1ec592';
            const mapsUrl = item.maps_url;
            const isAuthenticated = Boolean(authenticated);

            const minutesInt = (item.ultima_diff_minutes !== null && item.ultima_diff_minutes !== undefined) ? Math.round(item.ultima_diff_minutes) : null;
            const updatedClass = (nivelPercent > 25) ? 'updated--white' : 'updated--black';
            card.innerHTML = `
                <div class="fuel-card__body fuel-card__body--compact">
                    <div class="fuel-card__gauge-wrapper">
                        <div class="semi-gauge" style="--fuel-level: ${nivelPercent}; --fuel-color: ${fuelColor};" role="img" aria-label="Nível ${escapeHtml(nivelDisplay)} de ${escapeHtml(item.nome || '')}">
                            <div class="semi-gauge__dial">
                                <span>${escapeHtml(nivelDisplay)}</span>
                            </div>
                        </div>
                    </div>

                    <div class="fuel-card__body-meta">
                        <h3>${escapeHtml(local)}</h3>
                        <p class="fuel-card__stat">Autonomia ≈ ${escapeHtml(autonomia)}</p>
                        ${item.litros_disponiveis !== null && item.litros_disponiveis !== undefined ? `<p class="fuel-card__capacity">Cabem ${item.litros_disponiveis} litros</p>` : ''}
                        <div class="fuel-card__status-row">
                            ${item.status_online ? '' : `<div class="fuel-card__status fuel-card__status--offline"><span class="fuel-card__status-dot"></span>offline</div>`}
                            ${isAuthenticated && mapsUrl ? `<a href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener noreferrer" class="fuel-card__gps" title="Abrir no mapa"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-map-pin"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg></a>` : ''}
                        </div>
                    </div>
                </div>
                <div class="fuel-card__updated-badge ${updatedClass}">${minutesInt !== null ? `Atualizado à ${minutesInt} minutos` : 'Atualizado à —'}</div>
            `;

            fragment.appendChild(card);
        });

        grid.replaceChildren(fragment);
    };

    const authFromDom = document.body?.dataset?.auth === '1';

    const fetchAndRender = async () => {
        try {
            const response = await fetch('/api/fuel-levels', { cache: 'no-store', credentials: 'same-origin' });
            if (!response.ok) return;
            const data = await response.json();
            if (data && Array.isArray(data.items)) {
                const isAuthenticated = data.is_authenticated ?? authFromDom;
                renderCards(data.items, data.brasilia_now, isAuthenticated);
            }
        } catch (err) {
            console.warn('Falha ao atualizar níveis de combustível', err);
        }
    };

    // Primeiro carregamento imediato e depois a cada 5s
    fetchAndRender();
    setInterval(fetchAndRender, 5000);
}
