# Guía práctica del widget "ExpAvatarPopup"

El widget **ExpAvatarPopup** le permite mostrar el avatar de la persona responsable
de un registro y mantener esa información actualizada en tiempo real gracias al
bus de Odoo. Esta guía busca explicarle cómo integrarlo en otros módulos,
qué decisiones debe tomar en el backend y qué evitar en el proceso.

## ¿Cuándo conviene usarlo?

Úselo cuando tenga un campo `Many2one` ligado (directa o indirectamente) a un
empleado y necesite que el cambio de responsable se refleje al instante para
otros usuarios sin recargar la pantalla. Es ideal en compras, gastos, proyectos o
cualquier flujo colaborativo donde la persona asignada cambie con frecuencia.

## Antes de empezar

* Identifique el campo `Many2one` que apunta al empleado responsable.
* Verifique si ese campo apunta directo a `hr.employee` o si llega al empleado a
  través de otro modelo.
* Defina un nombre de canal único que combine el modelo y el identificador del
  registro (por ejemplo `purchase.request/42`).

## Cómo funciona, a grandes rasgos

1. El campo `Many2one` se renderiza con el widget `ExpAvatarPopup` en la vista
   XML.
2. El cliente web pregunta al backend la configuración usando
   `get_avatar_widget_config`.
3. Con esa configuración el widget se suscribe al canal correcto del bus,
   interpreta qué información necesita de cada notificación y resuelve qué avatar
   mostrar.
4. Cuando su backend emite una notificación (por ejemplo al reasignar el
   responsable), el widget compara la información recibida, refresca el campo y
   actualiza la tarjeta emergente.

Considere el widget como un "escucha y actualiza" altamente configurable: usted
proporciona las reglas y él mantiene sincronizada la interfaz para todas las
personas conectadas.

## Integración paso a paso

### 1. Prepare su modelo

Implemente el método `get_avatar_widget_config(self, record_id=False, field_name=False)`
en el modelo que contiene el `Many2one`.

#### Ejemplo básico (campo directo a `hr.employee`)

```python
def get_avatar_widget_config(self, record_id=False, field_name=False):
    self.ensure_one()
    return {
        "channel_name": f"purchase.request/{self.id}",
        "notification_type": "purchase.avatar/update",
        "payload_key": "request_id",
        # No necesita relation_employee_field porque responsible_id ya apunta a hr.employee
    }
```

#### Ejemplo con modelo intermedio

```python
def get_avatar_widget_config(self, record_id=False, field_name=False):
    self.ensure_one()
    return {
        "channel_name": f"purchase.responsible/{self.id}",
        "notification_type": "purchase.avatar/update",
        "payload_key": "quotation_id",
        "relation_employee_field": "employee_id",  # responsible_id -> purchase.member -> employee_id
        "employee_model": "hr.employee",  # opcional, use el suyo si es distinto
        "fallback_delay": 120000,  # reintenta cada 2 minutos si el bus se cae
    }
```

#### ¿Qué significa cada clave?

* **`channel_name`** *(obligatorio)*: canal único del bus. Mezcla el nombre del
  modelo con el `record_id` para evitar cruces entre registros.
* **`notification_type`** *(obligatorio)*: etiqueta que enviará desde Python. El
  widget ignora notificaciones con un tipo distinto.
* **`payload_key`** *(obligatorio)*: nombre de la clave que identifica al registro
  dentro de la carga útil. Debe coincidir exactamente con lo que manda en la
  notificación.
* **`relation_employee_field`** *(opcional)*: señala el campo `Many2one` que llega
  al empleado cuando su `Many2one` principal apunta a otro modelo.
* **`employee_model`** *(opcional)*: solo necesario si el empleado reside en otro
  modelo distinto a `hr.employee`.
* **`fallback_delay`** *(opcional)*: intervalo en milisegundos para el modo
  *polling* cuando el bus no responde.

El widget convierte estas claves de *snake_case* a *camelCase* por usted, así que no
necesita adaptarlas manualmente para el frontend.

### 2. Declare el widget en la vista XML

```xml
<field name="responsible_id" widget="ExpAvatarPopup"/>
```

No añada atributos `options` ni campos auxiliares: toda la configuración llega
mediante el método Python anterior.

### 3. Envíe notificaciones cuando cambie el responsable

Cree un método auxiliar que emita mensajes cada vez que el responsable se asigne
por primera vez o cambie. Incluya en el `payload` la clave definida en
`payload_key` y el identificador del empleado que debe mostrarse.

```python
def _notify_avatar_update(self, reason="update"):
    bus = self.env["bus.bus"]
    timestamp = fields.Datetime.now()
    for record in self:
        config = record.get_avatar_widget_config(record.id, "responsible_id")
        channel = config.get("channel_name")
        if not channel:
            continue
        payload = {
            "quotation_id": record.id,  # coincide con payload_key
            "employee_id": record.responsible_id.employee_id.id,
            "reason": reason,
            "timestamp": timestamp,
        }
        bus._sendone(channel, config.get("notification_type"), payload)
```

Invoque este método desde `create`, `write`, botones de asignación o cualquier
punto donde cambie al responsable.

## Lista de verificación rápida

* [ ] El campo en la vista usa `widget="ExpAvatarPopup"`.
* [ ] El modelo implementa `get_avatar_widget_config` y devuelve al menos
      `channel_name`, `notification_type` y `payload_key`.
* [ ] Las notificaciones envían el identificador esperado por `payload_key` y el
      ID del empleado.
* [ ] El canal incluye el ID del registro o un identificador único.
* [ ] Se manejan escenarios sin responsable asignado (el widget muestra un estado
      vacío sin romperse).

## Problemas frecuentes y cómo solucionarlos

| Síntoma | Posible causa | Cómo resolver |
| --- | --- | --- |
| El avatar no aparece o muestra el genérico | El campo Many2one no llega a `hr.employee` | Revise `relation_employee_field` y que el empleado exista |
| El avatar nunca se actualiza | El canal o `notification_type` no coinciden entre backend y frontend | Compare lo que devuelve `get_avatar_widget_config` con lo que usa en `_sendone` |
| Se reciben notificaciones de otros registros | El canal es demasiado genérico | Incluya el ID del registro en `channel_name` |
| Cambios desde otra sesión no refrescan | No se está llamando a `_notify_avatar_update` | Invoque el método en `create`, `write` y acciones manuales |
| El bus se cae y no vuelve a sincronizar | `fallback_delay` demasiado alto o sin definir | Ajuste el valor o deje que use el predeterminado del widget |

## Buenas prácticas

* Ponga nombre claro a los canales para que sea fácil rastrear mensajes en los
  logs (`purchase.request/42`, `expense.sheet/15`, etc.).
* Evite campos computados o temporales: si necesita más datos para la vista,
  inclúyalos directamente en el diccionario que retorna `get_avatar_widget_config`.
* Pruebe siempre con dos usuarios (dos navegadores o ventana privada) para
  confirmar la actualización en vivo.
* Durante el desarrollo puede registrar las notificaciones con `_logger.info`
  para depurar y eliminar esos registros antes de llegar a producción.
