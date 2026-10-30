import type { Metadata } from "next";
import Link from "next/link";
import { CircleUserRound, Settings } from "lucide-react";
import { Notice } from "@/components/ui/notice";
import { AccountProfile } from "@/features/authentication/account-panel";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">Personal workspace</p>
        <h1>Your profile</h1>
        <p>Update your profile, manage your account session, or delete your account.</p>
      </div>
      <Notice title="Your profile is account-protected">
        Profile changes are saved securely to your account after sign-in.
      </Notice>
      <section aria-labelledby="profile-heading" className="card workspace-panel" style={{ marginTop: "1.25rem" }}>
        <div className="panel-heading">
          <div>
            <h2 id="profile-heading">Account information</h2>
            <p>Sign-in is required to view your account details.</p>
          </div>
          <CircleUserRound aria-hidden="true" />
        </div>
        <AccountProfile />
        <Link className="button button-secondary" href="/settings">
          <Settings aria-hidden="true" /> Open preferences
        </Link>
      </section>
    </section>
  );
}
