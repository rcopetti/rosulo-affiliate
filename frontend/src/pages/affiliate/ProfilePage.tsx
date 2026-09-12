import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getProfile, updateProfile } from '@/api/affiliate/profile';
import { ProfileForm } from '@/components/affiliate/ProfileForm';
import { KycUploader } from '@/components/affiliate/KycUploader';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function ProfilePage() {
  const { data: account, isLoading, refetch } = useQuery({ queryKey: ['affiliate-account'], queryFn: getProfile });
  const queryClient = useQueryClient();
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-account'] });
      toast.add({ title: 'Profile saved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not save profile', variant: 'error' }),
  });

  if (isLoading || !account) return <p className="text-slate-600">Loading profile…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
      <Card>
        <CardHeader>
          <CardTitle>Account details</CardTitle>
        </CardHeader>
        <ProfileForm account={account} onSubmit={(d) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Tax documents</CardTitle>
        </CardHeader>
        <p className="mb-4 text-sm text-fg-muted">
          Your required IRS form is determined by your US/foreign status and whether you are an individual or business. Upload it separately for review.
        </p>
        <KycUploader
          taxStatus={account.tax_status}
          taxEntityType={account.tax_entity_type}
          documents={account.documents}
          onUpload={() => refetch()}
        />
      </Card>
    </div>
  );
}
