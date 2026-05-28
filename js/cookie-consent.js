// js/cookie-consent.js
(function() {
    // Si ya tomó una decisión en esta sesión o anteriormente, no mostrar
    if (localStorage.getItem('cookie-consent-choice') !== null) {
        return;
    }

    // Crear estilos
    const style = document.createElement('style');
    style.innerHTML = `
        .pk-cookie-banner {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(150%);
            width: 90%;
            max-width: 560px;
            background: rgba(10, 25, 47, 0.96);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(240, 180, 41, 0.35);
            border-radius: 16px;
            padding: 1.5rem;
            z-index: 100000;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
            transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            text-align: left;
        }
        .pk-cookie-banner.show {
            transform: translateX(-50%) translateY(0);
        }
        .pk-cookie-header {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            color: #f0b429;
            font-weight: 800;
            font-size: 1.15rem;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .pk-cookie-text {
            color: #a8b2d1;
            font-size: 0.88rem;
            line-height: 1.5;
            margin: 0;
        }
        .pk-cookie-text a {
            color: #f0b429;
            text-decoration: none;
            font-weight: 600;
            border-bottom: 1px dashed rgba(240, 180, 41, 0.5);
            transition: all 0.2s ease;
        }
        .pk-cookie-text a:hover {
            color: #d49f20;
            border-bottom-color: #d49f20;
        }
        .pk-cookie-actions {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            align-items: center;
        }
        .pk-cookie-btn {
            padding: 0.6rem 1.4rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            border: none;
            outline: none;
        }
        .pk-cookie-btn-accept {
            background: linear-gradient(135deg, #f0b429, #d49f20);
            color: #0a192f;
            box-shadow: 0 4px 12px rgba(240, 180, 41, 0.2);
        }
        .pk-cookie-btn-accept:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(240, 180, 41, 0.3);
        }
        .pk-cookie-btn-accept:active {
            transform: translateY(0);
        }
        .pk-cookie-btn-reject {
            background: transparent;
            color: #8892b0;
            border: 1px solid rgba(136, 146, 176, 0.3);
        }
        .pk-cookie-btn-reject:hover {
            background: rgba(136, 146, 176, 0.08);
            color: #ccd6f6;
            border-color: rgba(136, 146, 176, 0.5);
        }
        @media (max-width: 480px) {
            .pk-cookie-banner {
                bottom: 12px;
                padding: 1.25rem;
                width: 92%;
            }
            .pk-cookie-actions {
                flex-direction: column-reverse;
                gap: 0.75rem;
                width: 100%;
            }
            .pk-cookie-btn {
                width: 100%;
                text-align: center;
                padding: 0.7rem;
            }
        }
    `;
    document.head.appendChild(style);

    // Crear elemento banner
    const banner = document.createElement('div');
    banner.className = 'pk-cookie-banner';
    banner.innerHTML = `
        <div class="pk-cookie-header">
            <span>🍪</span> Configuración de Cookies
        </div>
        <p class="pk-cookie-text">
            En PREDIKTOR utilizamos cookies propias y tecnologías de terceros (como Google AdSense) para analizar tu navegación, recordar tus preferencias y personalizar la publicidad que se te muestra. Al pulsar en "Aceptar Todo", prestas tu consentimiento. Puedes conocer más en nuestra <a href="privacy.html">Política de Privacidad</a>.
        </p>
        <div class="pk-cookie-actions">
            <button class="pk-cookie-btn pk-cookie-btn-reject" id="pk-cookie-reject">Rechazar</button>
            <button class="pk-cookie-btn pk-cookie-btn-accept" id="pk-cookie-accept">Aceptar Todo</button>
        </div>
    `;
    document.body.appendChild(banner);

    // Activar animación de entrada tras 1.2s
    setTimeout(() => {
        banner.classList.add('show');
    }, 1200);

    // Handlers
    document.getElementById('pk-cookie-accept').addEventListener('click', () => {
        localStorage.setItem('cookie-consent-choice', 'accepted');
        banner.classList.remove('show');
        setTimeout(() => banner.remove(), 600);
    });

    document.getElementById('pk-cookie-reject').addEventListener('click', () => {
        localStorage.setItem('cookie-consent-choice', 'rejected');
        banner.classList.remove('show');
        setTimeout(() => banner.remove(), 600);
    });
})();
