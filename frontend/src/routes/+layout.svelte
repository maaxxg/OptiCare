<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import '#lib/styles/global.css';
	import type { LayoutProps } from './$types';
	import { isLoggedIn } from '#lib/stores/auth.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let { children }: LayoutProps = $props();

	onMount(() => {
		const loginPath = resolve('/login');
		const isMobileRoute = page.url.pathname.includes('/mobilno');
		if (!isLoggedIn() && !page.url.pathname.startsWith(loginPath) && !isMobileRoute) {
			goto(loginPath);
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
