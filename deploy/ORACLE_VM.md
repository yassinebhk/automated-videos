# Crear la VM en Oracle Cloud (Always Free)

Sigue estos pasos en el navegador. Cuando termines, dame **IP pública** + **ruta del SSH key** y yo instalo el resto.

## 1. Cuenta
1. https://www.oracle.com/cloud/free/ → "Start for free"
2. Rellena datos. Pide tarjeta para verificar identidad — **NO cobra** (es Always Free).
3. Elige una región cercana (ej. Spain Central / Frankfurt).

## 2. Crear la instancia (VM)
1. Menú ☰ → **Compute → Instances → Create instance**
2. **Name**: `videogen`
3. **Image & shape** → Edit:
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)** → 2 OCPU / 12 GB (dentro del Always Free de 4/24)
     - Si no hay disponibilidad de Ampere, usa **VM.Standard.E2.1.Micro** (más lento pero vale)
4. **SSH keys**: "Generate a key pair for me" → **Download private key** (guárdalo, ej. `~/Downloads/videogen.key`)
5. **Create**. Espera a que esté "Running" y copia la **Public IP address**.

## 3. Abrir el puerto de la UI (opcional, para web)
Solo si quieres la UI web por URL pública (el bot no lo necesita):
1. Instancia → **Virtual Cloud Network** → Security Lists → Default
2. Add Ingress Rule: Source `0.0.0.0/0`, IP Protocol TCP, Destination port **5005**

## 4. Permisos del key (en tu Mac)
```bash
chmod 600 ~/Downloads/videogen.key
```

## 5. Dámelo
Pásame:
- **IP pública** (ej. 140.238.x.x)
- **Ruta del key** (ej. ~/Downloads/videogen.key)

Y ejecuto: `bash deploy/push.sh <IP> <key>` → instala ffmpeg, deps, fuentes, música, copia tus secretos y arranca el bot como servicio 24/7.
