# Manual de IT y Seguridad - Nubbix

## Solicitud de Accesos y Permisos
Los accesos a sistemas (GitHub, AWS, VPN, GCP, Jira) deben solicitarse mediante ticket en la mesa de ayuda de IT.
El tiempo estándar de resolución para permisos de lectura es de 4 horas hábiles. Accesos con permisos de Administrador o Producción requieren doble aprobación: el Tech Lead del equipo y el CISO de Nubbix.

## Equipos de Trabajo y Hardware
A cada nuevo integrante se le asigna una MacBook Pro M2/M3 o un Dell XPS de gama alta con 32GB RAM.
La renovación de equipos de cómputo se realiza cada 3 años.
En caso de pérdida, robo o daño grave del equipo corporativo, el colaborador debe:
1. Notificar inmediatamente al canal de Slack #it-ops y enviar un email a it@nubbix.com.
2. Presentar la denuncia policial correspondiente dentro de las 48 horas en caso de robo fuera del domicilio.

## Políticas de Contraseñas y MFA
Todos los colaboradores deben activar Autenticación de Dos Factores (MFA) vía aplicación Google Authenticator o 1Password en todas las cuentas corporativas.
Las contraseñas de Google Workspace expiran cada 90 días y deben poseer un mínimo de 16 caracteres.
Está estrictamente prohibido compartir credenciales corporativas a través de Slack o correo electrónico.

## Seguridad de Datos y Backups
Toda la información sensible de clientes debe almacenarse exclusivamente en Google Drive corporativo o en los buckets de AWS autorizados por IT, nunca en discos locales sin cifrar.
Los backups de las bases de datos productivas se ejecutan de forma automática cada 6 horas y se retienen por 90 días.
El uso de la VPN corporativa es obligatorio al conectarse desde redes Wi-Fi públicas, como aeropuertos, cafés u hoteles.

## Soporte Técnico y Mesa de Ayuda
Los incidentes técnicos (fallas de hardware, errores de acceso, problemas de conectividad) se reportan por el canal de Slack #it-help o mediante ticket en la mesa de ayuda.
El SLA de primera respuesta es de 2 horas hábiles para incidentes críticos y de 24 horas hábiles para consultas generales.
Si el incidente ocurre durante un viaje de trabajo, el colaborador puede solicitar un equipo de reemplazo temporal coordinando con IT y, de corresponder, gestionar el reintegro de los gastos asociados con Finance.

## Offboarding y Baja de Colaboradores
Cuando un colaborador deja Nubbix, IT desactiva todos sus accesos (GitHub, AWS, VPN, Google Workspace) dentro de las 24 horas de notificada la baja por People.
El equipo asignado (MacBook o Dell XPS) debe devolverse a la oficina central o a un punto de retiro coordinado con IT antes del último día hábil.
Las credenciales y tokens de API personales deben rotarse o revocarse como parte del checklist de baja.