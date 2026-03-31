import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SyncSession

from fan_experience.db.models import Plan, PlanStatus, PlanVersion
from fan_experience.schemas.agent import PlanProposal


# saving validated plan proposals as incrementing plan versions.
class PlanService:
    def __init__(self, session: SyncSession):
        self._session = session

    def save_plan_version(
        self,
        plan_id: uuid.UUID,
        proposal: PlanProposal,
        confidence_result: dict,
        trigger_reason: str,
        agent_reasoning: str,
    ) -> PlanVersion:
        max_version = self._session.execute(
            select(func.coalesce(func.max(PlanVersion.version_number), 0)).where(
                PlanVersion.plan_id == plan_id
            )
        ).scalar_one()
        next_version = max_version + 1

        version = PlanVersion(
            plan_id=plan_id,
            version_number=next_version,
            payload_json={
                "shortlist": [
                    option.model_dump(mode="json") for option in proposal.shortlist
                ],
                "plan_summary": proposal.plan_summary,
            },
            confidence_score=confidence_result["overall"],
            confidence_breakdown_json=confidence_result,
            trigger_reason=trigger_reason,
            agent_reasoning=agent_reasoning,
            conversation_history_json=proposal.conversation_history,
        )
        self._session.add(version)

        # only transition to active if not already in that state
        plan = self._session.get(Plan, plan_id)
        if plan.status != PlanStatus.ACTIVE:
            plan.status = PlanStatus.ACTIVE
        self._session.commit()

        return version
