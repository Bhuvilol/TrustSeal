from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..dependencies import IngestAuthContext, require_device_ingest_auth, require_verifier_ingest_auth
from ..database import get_db
from ..models.custody_transfer import CustodyTransfer
from ..models.telemetry_event import TelemetryEvent
from ..schemas.common import ApiError, ApiSuccess
from ..schemas.ingest import CustodyIngestRequest, TelemetryIngestRequest
from ..services.idempotency_service import idempotency_service
from ..services.ingest_verification_service import ingest_verification_service
from ..services.state_machine_service import state_machine_service
from ..services.telemetry_stream_service import telemetry_stream_service

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post(
    "/ingest/telemetry",
    response_model=ApiSuccess,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_telemetry(
    payload: TelemetryIngestRequest,
    auth_ctx: IngestAuthContext = Depends(require_device_ingest_auth),
    db: Session = Depends(get_db),
) -> ApiSuccess | JSONResponse:
    if auth_ctx.identity and auth_ctx.identity != payload.device_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ApiError(
                error_code="DEVICE_IDENTITY_MISMATCH",
                message="Authenticated device identity does not match payload device_id",
                details={"header_device_id": auth_ctx.identity, "payload_device_id": payload.device_id},
            ).model_dump(),
        )

    verification = ingest_verification_service.verify_telemetry(payload)
    if not verification.ok:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ApiError(
                error_code=verification.error_code or "INVALID_TELEMETRY_PACKET",
                message=verification.message or "Telemetry packet verification failed",
            ).model_dump(),
        )

    duplicate = idempotency_service.telemetry_exists(
        db,
        event_id=payload.event_id,
        idempotency_key=payload.idempotency_key,
    )
    if duplicate:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code="DUPLICATE_EVENT",
                message="Telemetry event already processed",
                details={"event_id": payload.event_id},
            ).model_dump(),
        )

    replay_reason = idempotency_service.telemetry_replay_reason(
        db,
        device_id=payload.device_id,
        seq_no=payload.seq_no,
        ts=verification.normalized_ts,
    )
    if replay_reason:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code=replay_reason,
                message="Telemetry replay or stale event rejected",
                details={"event_id": payload.event_id},
            ).model_dump(),
        )

    if not telemetry_stream_service.stream_enabled:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ApiError(
                error_code="QUEUE_UNAVAILABLE",
                message="Redis stream is disabled; cannot enqueue telemetry event",
            ).model_dump(),
        )

    metrics = {
        "temperature_c": payload.temperature_c,
        "humidity_pct": payload.humidity_pct,
        "shock_g": payload.shock_g,
        "light_lux": payload.light_lux,
        "tilt_deg": payload.tilt_deg,
        "battery_pct": payload.battery_pct,
    }
    telemetry = TelemetryEvent(
        event_id=payload.event_id,
        shipment_id=uuid.UUID(payload.shipment_id),
        device_id=uuid.UUID(payload.device_id),
        ts=verification.normalized_ts,
        seq_no=payload.seq_no,
        metrics=metrics,
        gps=payload.gps.model_dump() if payload.gps else None,
        hash_alg=payload.hash_alg,
        payload_hash=payload.payload_hash,
        sig_alg=payload.sig_alg,
        signature=payload.signature,
        pubkey_id=payload.pubkey_id,
        idempotency_key=payload.idempotency_key,
        verification_status="valid",
        ingest_status="verified",
    )
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)

    stream_id = telemetry_stream_service.publish_sensor_log(
        {
            "event_type": "telemetry",
            "event_id": payload.event_id,
            "shipment_id": payload.shipment_id,
            "device_id": payload.device_id,
            "ts": payload.ts,
            "seq_no": payload.seq_no,
            "metrics": metrics,
            "gps": payload.gps.model_dump() if payload.gps else None,
            "payload_hash": payload.payload_hash,
            "signature": payload.signature,
            "idempotency_key": payload.idempotency_key,
        }
    )
    if not stream_id:
        transition = state_machine_service.ensure_transition(
            machine="telemetry_ingest",
            from_state=telemetry.ingest_status,
            to_state="verified",
        )
        if transition.ok:
            telemetry.ingest_status = "verified"
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ApiError(
                error_code="QUEUE_ENQUEUE_FAILED",
                message="Failed to enqueue telemetry event",
                details={"event_id": payload.event_id},
            ).model_dump(),
        )

    transition = state_machine_service.ensure_transition(
        machine="telemetry_ingest",
        from_state=telemetry.ingest_status,
        to_state="queued",
    )
    if not transition.ok:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code="INVALID_STATE_TRANSITION",
                message=transition.error or "Invalid telemetry state transition",
                details={"event_id": payload.event_id},
            ).model_dump(),
        )
    telemetry.ingest_status = "queued"
    db.commit()

    return ApiSuccess(
        data={
            "accepted": True,
            "event_id": payload.event_id,
            "shipment_id": payload.shipment_id,
            "ingest_status": "queued",
            "stream": "telemetry_stream",
            "stream_event_id": stream_id,
            "received_at": _now_iso(),
        }
    )


@router.post(
    "/ingest/custody",
    response_model=ApiSuccess,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_custody(
    payload: CustodyIngestRequest,
    auth_ctx: IngestAuthContext = Depends(require_verifier_ingest_auth),
    db: Session = Depends(get_db),
) -> ApiSuccess | JSONResponse:
    if auth_ctx.identity and auth_ctx.identity != payload.verifier_device_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ApiError(
                error_code="VERIFIER_IDENTITY_MISMATCH",
                message="Authenticated verifier identity does not match payload verifier_device_id",
                details={
                    "header_verifier_device_id": auth_ctx.identity,
                    "payload_verifier_device_id": payload.verifier_device_id,
                },
            ).model_dump(),
        )

    verification = ingest_verification_service.verify_custody(payload)
    if not verification.ok:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ApiError(
                error_code=verification.error_code or "INVALID_CUSTODY_PACKET",
                message=verification.message or "Custody packet verification failed",
            ).model_dump(),
        )

    duplicate = idempotency_service.custody_exists(
        db,
        custody_event_id=payload.custody_event_id,
        idempotency_key=payload.idempotency_key,
    )
    if duplicate:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code="DUPLICATE_EVENT",
                message="Custody event already processed",
                details={"custody_event_id": payload.custody_event_id},
            ).model_dump(),
        )

    replay_reason = idempotency_service.custody_replay_reason(
        db,
        verifier_device_id=payload.verifier_device_id,
        shipment_id=payload.shipment_id,
        ts=verification.normalized_ts,
    )
    if replay_reason:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code=replay_reason,
                message="Custody replay or stale event rejected",
                details={"custody_event_id": payload.custody_event_id},
            ).model_dump(),
        )

    if not telemetry_stream_service.stream_enabled:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ApiError(
                error_code="QUEUE_UNAVAILABLE",
                message="Redis stream is disabled; cannot enqueue custody event",
            ).model_dump(),
        )

    transfer = CustodyTransfer(
        custody_event_id=payload.custody_event_id,
        shipment_id=uuid.UUID(payload.shipment_id),
        leg_id=uuid.UUID(payload.leg_id),
        verifier_user_id=uuid.UUID(payload.verifier_user_id),
        verifier_device_id=uuid.UUID(payload.verifier_device_id),
        ts=verification.normalized_ts,
        fingerprint_result=payload.fingerprint_result,
        fingerprint_score=payload.fingerprint_score,
        fingerprint_template_id=payload.fingerprint_template_id,
        digital_signer_address=payload.digital_signer_address,
        approval_message_hash=payload.approval_message_hash,
        signature=payload.signature,
        sig_alg=payload.sig_alg,
        verification_status="valid",
        ingest_status="verified",
        idempotency_key=payload.idempotency_key,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    stream_id = telemetry_stream_service.publish_custody_event(
        {
            "event_type": "custody",
            "custody_event_id": payload.custody_event_id,
            "shipment_id": payload.shipment_id,
            "leg_id": payload.leg_id,
            "verifier_user_id": payload.verifier_user_id,
            "verifier_device_id": payload.verifier_device_id,
            "ts": payload.ts,
            "fingerprint_result": payload.fingerprint_result,
            "fingerprint_score": payload.fingerprint_score,
            "fingerprint_template_id": payload.fingerprint_template_id,
            "digital_signer_address": payload.digital_signer_address,
            "approval_message_hash": payload.approval_message_hash,
            "signature": payload.signature,
            "idempotency_key": payload.idempotency_key,
        }
    )
    if not stream_id:
        transfer.ingest_status = "verified"
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ApiError(
                error_code="QUEUE_ENQUEUE_FAILED",
                message="Failed to enqueue custody event",
                details={"custody_event_id": payload.custody_event_id},
            ).model_dump(),
        )

    transition = state_machine_service.ensure_transition(
        machine="telemetry_ingest",
        from_state=transfer.ingest_status,
        to_state="queued",
    )
    if not transition.ok:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiError(
                error_code="INVALID_STATE_TRANSITION",
                message=transition.error or "Invalid custody state transition",
                details={"custody_event_id": payload.custody_event_id},
            ).model_dump(),
        )
    transfer.ingest_status = "queued"
    db.commit()

    return ApiSuccess(
        data={
            "accepted": True,
            "custody_event_id": payload.custody_event_id,
            "shipment_id": payload.shipment_id,
            "ingest_status": "queued",
            "stream": "custody_stream",
            "stream_event_id": stream_id,
            "received_at": _now_iso(),
        }
    )
