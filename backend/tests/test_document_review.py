import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_api_key
from app.db.models import Affiliate, AffiliateAccount, AffiliateDocument, Tenant, TenantUser
from app.db.session import async_session


async def create_affiliate(client: AsyncClient, tenant: Tenant, email: str):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]
    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": email},
    )
    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite.json()["token"],
            "email": email,
            "password": "secret123",
            "name": "Document Review Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    account_id = accept.json()["account"]["id"]
    affiliates = await client.get(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    affiliate = next(item for item in affiliates.json() if item["account_id"] == account_id)
    return accept.json()["token"], admin_token, affiliate["id"]


@pytest.mark.asyncio
async def test_missing_and_pending_documents_block_payout_requests(
    client: AsyncClient, tenant: Tenant, tenant_user, monkeypatch
):
    affiliate_token, _, _ = await create_affiliate(
        client, tenant, "document-review-missing@example.com"
    )
    headers = {
        "Authorization": f"Bearer {affiliate_token}",
        "X-Tenant-Id": str(tenant.id),
    }

    missing = await client.get("/api/v1/affiliate/documents", headers=headers)
    assert missing.status_code == 200
    assert missing.json()["payout_eligibility"]["eligible"] is False
    assert missing.json()["payout_eligibility"]["status"] == "missing"

    blocked = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=headers,
        json={"currency": "USD"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Required tax document is missing"

    monkeypatch.setattr(
        "app.services.affiliate_account.put_document",
        lambda document_id, content: f"private/{document_id}",
    )
    uploaded = await client.post(
        "/api/v1/affiliate/documents",
        headers=headers,
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"tax document", "application/pdf")},
    )
    assert uploaded.status_code == 200

    pending = await client.get("/api/v1/affiliate/documents", headers=headers)
    assert pending.status_code == 200
    assert pending.json()["documents"][0]["status"] == "pending"
    assert pending.json()["payout_eligibility"]["status"] == "pending"


@pytest.mark.asyncio
async def test_rejection_requires_reason_and_records_tenant_reviewer(
    client: AsyncClient, tenant: Tenant, tenant_user, monkeypatch
):
    affiliate_token, admin_token, affiliate_id = await create_affiliate(
        client, tenant, "document-review-rejected@example.com"
    )
    monkeypatch.setattr(
        "app.services.affiliate_account.put_document",
        lambda document_id, content: f"private/{document_id}",
    )
    affiliate_headers = {
        "Authorization": f"Bearer {affiliate_token}",
        "X-Tenant-Id": str(tenant.id),
    }
    uploaded = await client.post(
        "/api/v1/affiliate/documents",
        headers=affiliate_headers,
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"tax document", "application/pdf")},
    )
    document_id = uploaded.json()["id"]
    review_url = (
        f"/api/v1/admin/affiliates/{affiliate_id}/documents/{document_id}/review"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    missing_reason = await client.post(
        review_url,
        headers=admin_headers,
        json={"status": "rejected"},
    )
    assert missing_reason.status_code == 422

    rejected = await client.post(
        review_url,
        headers=admin_headers,
        json={"status": "rejected", "rejection_reason": "The form is unsigned"},
    )
    assert rejected.status_code == 200

    status = await client.get("/api/v1/affiliate/documents", headers=affiliate_headers)
    document = status.json()["documents"][0]
    assert document["status"] == "rejected"
    assert document["review_history"][0]["reviewer"]["id"] == str(tenant_user.id)
    assert document["review_history"][0]["reviewed_at"] is not None
    assert document["review_history"][0]["rejection_reason"] == "The form is unsigned"
    assert status.json()["payout_eligibility"]["eligible"] is False


@pytest.mark.asyncio
async def test_legacy_unscoped_approval_does_not_grant_payout_eligibility(
    client: AsyncClient, tenant: Tenant, tenant_user
):
    affiliate_token, _, affiliate_id = await create_affiliate(
        client, tenant, "document-review-legacy@example.com"
    )
    async with async_session() as db:
        affiliate = await db.get(Affiliate, uuid.UUID(affiliate_id))
        affiliate.legacy_kyc_approved_for_payout = True
        document = AffiliateDocument(
            affiliate_account_id=affiliate.affiliate_account_id,
            document_type="W-9",
            document_url="private/legacy",
            content_type="application/pdf",
            legacy_approved=True,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        assert document.legacy_approved is True

    headers = {
        "Authorization": f"Bearer {affiliate_token}",
        "X-Tenant-Id": str(tenant.id),
    }
    status = await client.get("/api/v1/affiliate/documents", headers=headers)
    assert status.status_code == 200
    assert status.json()["documents"] == []
    assert status.json()["payout_eligibility"]["status"] == "missing"

    blocked = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=headers,
        json={"currency": "USD"},
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_document_copies_and_reviews_are_isolated_between_merchants(
    client: AsyncClient, tenant: Tenant, tenant_user, monkeypatch
):
    account = AffiliateAccount(
        email="document-review-multi-merchant@example.com",
        password_hash="unused",
        name="Multi Merchant Affiliate",
        country="US",
    )
    tenant_b = Tenant(name="second-merchant", api_key_hash=hash_api_key("tenant-b-key"))
    async with async_session() as db:
        db.add_all([account, tenant_b])
        await db.flush()
        affiliate_a = Affiliate(affiliate_account_id=account.id, tenant_id=tenant.id)
        affiliate_b = Affiliate(affiliate_account_id=account.id, tenant_id=tenant_b.id)
        reviewer_b = TenantUser(
            tenant_id=tenant_b.id,
            email="reviewer-b@example.com",
            password_hash="unused",
            name="Reviewer B",
            role="admin",
        )
        db.add_all([affiliate_a, affiliate_b, reviewer_b])
        await db.commit()
        account_id = str(account.id)
        affiliate_a_id = str(affiliate_a.id)
        affiliate_b_id = str(affiliate_b.id)
        tenant_b_id = str(tenant_b.id)
        reviewer_b_id = str(reviewer_b.id)

    affiliate_token = create_access_token(account_id)
    reviewer_a_token = create_access_token(
        tenant_user.id, extra={"tenant_id": str(tenant.id)}
    )
    reviewer_b_token = create_access_token(
        reviewer_b_id, extra={"tenant_id": tenant_b_id}
    )
    monkeypatch.setattr(
        "app.services.affiliate_account.put_document",
        lambda document_id, content: f"private/{document_id}",
    )
    monkeypatch.setattr("app.api.v1.admin.affiliates.get_document", lambda key, doc_id: b"secret")
    upload_a = await client.post(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": str(tenant.id),
        },
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"merchant a tax document", "application/pdf")},
    )
    document_a_id = upload_a.json()["id"]
    approve_a = await client.post(
        f"/api/v1/admin/affiliates/{affiliate_a_id}/documents/{document_a_id}/review",
        headers={"Authorization": f"Bearer {reviewer_a_token}"},
        json={"status": "approved"},
    )
    assert approve_a.status_code == 200

    status_b = await client.get(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": tenant_b_id,
        },
    )
    assert status_b.status_code == 200
    assert status_b.json()["documents"] == []
    assert status_b.json()["payout_eligibility"]["status"] == "missing"

    status_a = await client.get(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": str(tenant.id),
        },
    )
    assert status_a.json()["payout_eligibility"]["eligible"] is True
    merchants = await client.get(
        "/api/v1/affiliate/merchants",
        headers={"Authorization": f"Bearer {affiliate_token}"},
    )
    eligibility_by_tenant = {
        merchant["tenant_id"]: merchant["payout_eligibility"]
        for merchant in merchants.json()
    }
    assert eligibility_by_tenant[str(tenant.id)]["status"] == "approved"
    assert eligibility_by_tenant[tenant_b_id]["status"] == "missing"

    upload_b = await client.post(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": tenant_b_id,
        },
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"merchant b tax document", "application/pdf")},
    )
    document_b_id = upload_b.json()["id"]
    reject_b = await client.post(
        f"/api/v1/admin/affiliates/{affiliate_b_id}/documents/{document_b_id}/review",
        headers={"Authorization": f"Bearer {reviewer_b_token}"},
        json={"status": "rejected", "rejection_reason": "Merchant B needs a signed form"},
    )
    assert reject_b.status_code == 200
    status_b = await client.get(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": tenant_b_id,
        },
    )
    assert status_b.json()["payout_eligibility"]["status"] == "rejected"
    assert status_b.json()["payout_eligibility"]["reason"] == "Merchant B needs a signed form"

    upload_b_again = await client.post(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": tenant_b_id,
        },
        data={"type": "W-9"},
        files={"file": ("w9-new.pdf", b"replacement merchant b form", "application/pdf")},
    )
    status_b = await client.get(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": tenant_b_id,
        },
    )
    assert status_b.json()["payout_eligibility"]["status"] == "pending"
    assert status_b.json()["documents"][0]["id"] == upload_b_again.json()["id"]
    previous_rejection = next(
        document for document in status_b.json()["documents"] if document["id"] == document_b_id
    )
    assert previous_rejection["status"] == "rejected"
    assert previous_rejection["review_history"][0]["rejection_reason"] == "Merchant B needs a signed form"

    upload_a_again = await client.post(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": str(tenant.id),
        },
        data={"type": "W-9"},
        files={"file": ("w9-new.pdf", b"replacement tax document", "application/pdf")},
    )
    replacement_document_id = upload_a_again.json()["id"]
    status_a = await client.get(
        "/api/v1/affiliate/documents",
        headers={
            "Authorization": f"Bearer {affiliate_token}",
            "X-Tenant-Id": str(tenant.id),
        },
    )
    assert status_a.json()["payout_eligibility"]["status"] == "pending"
    assert status_a.json()["documents"][0]["id"] == replacement_document_id
    previous_document = next(
        document for document in status_a.json()["documents"] if document["id"] == document_a_id
    )
    assert previous_document["status"] == "approved"
    assert previous_document["review_history"][0]["reviewer"]["id"] == str(tenant_user.id)

    detail_b = await client.get(
        f"/api/v1/admin/affiliates/{affiliate_b_id}",
        headers={"Authorization": f"Bearer {reviewer_b_token}"},
    )
    assert detail_b.status_code == 200
    assert all(document["id"] != document_a_id for document in detail_b.json()["documents"])

    view_a_document_as_b = await client.get(
        f"/api/v1/admin/affiliates/{affiliate_b_id}/documents/{document_a_id}/view",
        headers={"Authorization": f"Bearer {reviewer_b_token}"},
    )
    assert view_a_document_as_b.status_code == 404

    review_a_document_as_b = await client.post(
        f"/api/v1/admin/affiliates/{affiliate_b_id}/documents/{document_a_id}/review",
        headers={"Authorization": f"Bearer {reviewer_b_token}"},
        json={"status": "rejected", "rejection_reason": "Wrong merchant"},
    )
    assert review_a_document_as_b.status_code == 404
