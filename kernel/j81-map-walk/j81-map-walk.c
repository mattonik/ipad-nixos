// SPDX-License-Identifier: GPL-2.0-only
/*
 * TEST ONLY, READ-ONLY. Reports how the calling process maps one virtual
 * address: its VMA flags and the page-table entries that translate it (raw
 * values, output physical address, memory-attribute index, shareability,
 * access permissions, execute-never bits) plus MAIR_EL1 and the attribute byte
 * the entry selects.
 *
 * It never reads or writes the mapped memory and has no MMIO of its own: it
 * only reads page-table entries of current->mm. The caller must have mapped
 * the address first (the userspace helper maps /dev/mem exactly as the GPU
 * core reader does) and asks about it from the same process.
 *
 *   /sys/devices/j81-map-walk/va    write "0x<virtual address>"  (0200)
 *   /sys/devices/j81-map-walk/walk  read: one line for that address (0400)
 */
#include <linux/device.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/mmap_lock.h>
#include <linux/of.h>
#include <linux/pgtable.h>
#include <linux/sched.h>
#include <asm/sysreg.h>

static struct device *walk_device;
static unsigned long query_va;

static ssize_t va_store(struct device *dev, struct device_attribute *attr,
			const char *buf, size_t count)
{
	unsigned long v;
	int ret = kstrtoul(buf, 16, &v);

	(void)dev;
	(void)attr;
	if (ret)
		return ret;
	query_va = v;
	return count;
}
static DEVICE_ATTR(va, 0200, NULL, va_store);

static ssize_t walk_show(struct device *dev, struct device_attribute *attr,
			 char *buf)
{
	struct mm_struct *mm = current->mm;
	struct vm_area_struct *vma;
	unsigned long va = query_va;
	unsigned long vm_flags = 0, vm_prot = 0;
	u64 pgd_v = 0, p4d_v = 0, pud_v = 0, pmd_v = 0, pte_v = 0;
	u64 mair = read_sysreg(mair_el1), tcr = read_sysreg(tcr_el1);
	const char *level = "none";
	bool have_vma = false, leaf = false;
	pgd_t *pgdp;
	p4d_t *p4dp;
	pud_t *pudp;
	pmd_t *pmdp;
	pte_t *ptep;
	u64 entry = 0, pa = 0;
	unsigned int attr_idx, sh, ap;

	(void)dev;
	(void)attr;
	if (!mm || !va)
		return sysfs_emit(buf, "result=no-query va=0x%lx\n", va);
	mmap_read_lock(mm);
	vma = find_vma(mm, va);
	if (vma && vma->vm_start <= va) {
		have_vma = true;
		vm_flags = vma->vm_flags;
		vm_prot = pgprot_val(vma->vm_page_prot);
	}
	pgdp = pgd_offset(mm, va);
	pgd_v = pgd_val(READ_ONCE(*pgdp));
	if (!pgd_none(READ_ONCE(*pgdp)) && !pgd_bad(READ_ONCE(*pgdp))) {
		p4dp = p4d_offset(pgdp, va);
		p4d_v = p4d_val(READ_ONCE(*p4dp));
		if (!p4d_none(READ_ONCE(*p4dp)) && !p4d_bad(READ_ONCE(*p4dp))) {
			pudp = pud_offset(p4dp, va);
			pud_v = pud_val(READ_ONCE(*pudp));
			if (pud_leaf(READ_ONCE(*pudp))) {
				level = "pud";
				entry = pud_v;
				leaf = true;
			} else if (!pud_none(READ_ONCE(*pudp)) && !pud_bad(READ_ONCE(*pudp))) {
				pmdp = pmd_offset(pudp, va);
				pmd_v = pmd_val(READ_ONCE(*pmdp));
				if (pmd_leaf(READ_ONCE(*pmdp))) {
					level = "pmd";
					entry = pmd_v;
					leaf = true;
				} else if (!pmd_none(READ_ONCE(*pmdp)) && !pmd_bad(READ_ONCE(*pmdp))) {
					ptep = pte_offset_kernel(pmdp, va);
					pte_v = pte_val(READ_ONCE(*ptep));
					level = "pte";
					entry = pte_v;
					leaf = true;
				}
			}
		}
	}
	mmap_read_unlock(mm);
	if (!leaf || !(entry & 1))
		return sysfs_emit(buf,
			"result=not-mapped va=0x%lx vma=%u vm_flags=0x%lx vm_page_prot=0x%lx pgd=0x%llx p4d=0x%llx pud=0x%llx pmd=0x%llx pte=0x%llx\n",
			va, have_vma, vm_flags, vm_prot, pgd_v, p4d_v, pud_v, pmd_v, pte_v);
	pa = entry & GENMASK_ULL(47, 12);
	attr_idx = (entry >> 2) & 7;
	sh = (entry >> 8) & 3;
	ap = (entry >> 6) & 3;
	return sysfs_emit(buf,
		"result=ok va=0x%lx level=%s vma=%u vm_flags=0x%lx vm_page_prot=0x%lx pgd=0x%llx p4d=0x%llx pud=0x%llx pmd=0x%llx pte=0x%llx output_pa=0x%llx attr_idx=%u mair_el1=0x%016llx mair_byte=0x%02llx sh=%u ap=%u af=%u ng=%u pxn=%u uxn=%u tcr_el1=0x%016llx page_size=%lu\n",
		va, level, have_vma, vm_flags, vm_prot, pgd_v, p4d_v, pud_v, pmd_v, pte_v, pa,
		attr_idx, mair, (mair >> (8 * attr_idx)) & 0xff, sh, ap,
		(unsigned int)((entry >> 10) & 1), (unsigned int)((entry >> 11) & 1),
		(unsigned int)((entry >> 53) & 1), (unsigned int)((entry >> 54) & 1),
		tcr, (unsigned long)PAGE_SIZE);
}
static DEVICE_ATTR(walk, 0400, walk_show, NULL);

static int __init j81_map_walk_init(void)
{
	int ret;

	if (!of_machine_is_compatible("apple,j81"))
		return -ENODEV;
	walk_device = root_device_register("j81-map-walk");
	if (IS_ERR(walk_device))
		return PTR_ERR(walk_device);
	ret = device_create_file(walk_device, &dev_attr_va);
	if (!ret)
		ret = device_create_file(walk_device, &dev_attr_walk);
	if (ret) {
		root_device_unregister(walk_device);
		return ret;
	}
	/* No exit path: stays for this boot. */
	__module_get(THIS_MODULE);
	return 0;
}
module_init(j81_map_walk_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only page-table walk for one address of the calling process (J81)");
