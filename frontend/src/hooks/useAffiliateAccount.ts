import { useQuery } from '@tanstack/react-query';
import { getProfile } from '@/api/affiliate/profile';

export function useAffiliateAccount() {
  return useQuery({
    queryKey: ['affiliate-account'],
    queryFn: getProfile,
    retry: 1,
  });
}
