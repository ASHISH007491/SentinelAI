import { apiClient } from "@/lib/api-client";

export interface TokenDto {
  access_token: string;
  token_type: string;
}

export const authService = {
  register: (email: string, password: string) =>
    apiClient.post<unknown>("/auth/register", { email, password }),
  login: (email: string, password: string) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return apiClient.postForm<TokenDto>("/auth/login", form);
  },
  me: () => apiClient.get<{ id: number; email: string }>("/auth/me"),
};
